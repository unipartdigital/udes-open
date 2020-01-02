# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

import logging
_logger = logging.getLogger(__name__)


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    # This is intended for when a pallet/package requires a second name to be
    # presented externally, e.g. when a package's (external) barcode format is
    # different to the internal one.
    u_external_name = fields.Char(string="External Name")

    def new_package_name(self):
        Sequence = self.env['ir.sequence']
        return Sequence.next_by_code('stock.quant.package') or _('Unknown Pack')

    def _default_package_name(self):
        MoveLine = self.env['stock.move.line']

        move_line_ids = self.env.context.get('move_line_ids')
        if move_line_ids:
            move_lines = MoveLine.browse(move_line_ids)
            name = move_lines.new_package_name()
        else:
            name = self.new_package_name()

        return name

    name = fields.Char(default=_default_package_name)

    def _prepare_info(self, extended=False, **kwargs):
        """
            Prepares the following info of the package in self:
            - id: int
            - name: string

            It also prepares the following extra info if they exist:
            - package_id: parent package of self
            - children_ids: children packages of self

            When extended is True also return:
            - location_id: [{stock.quants}]
            - quant_ids: [{stock.quants}]
        """
        self.ensure_one()

        info = {"id": self.id,
                "name": self.name}

        if self.package_id:
            info['package_id'] = self.package_id.id
        if self.children_ids:
            info['children_ids'] = self.children_ids.get_info(extended=extended, **kwargs)

        if extended:
            location_info = self.location_id.get_info()
            info['location_id'] = location_info[0] if location_info else {}
            info['quant_ids'] = self.quant_ids.get_info()

        return info

    def get_info(self, extended=False, **kwargs):
        """ Return a list with the information of each package in self.
        """
        res = []
        for pack in self:
            res.append(pack._prepare_info(extended=extended, **kwargs))

        return res

    def get_package(self, package_identifier, create=False, no_results=False):
        """ Get package from a name (i.e., barcode) or id.

            @param create: Boolean
                When it is True and package_identifier is a name,
                a package will be created if it does not exist

            @param no_results: Boolean
                Allows to return empty recordset when the package is
                not found
        """
        name = None
        if isinstance(package_identifier, int):
            domain = [('id', '=', package_identifier)]
        elif isinstance(package_identifier, str):
            domain = [('name', '=', package_identifier)]
            name = package_identifier
        else:
            raise ValidationError(_('Unable to create domain for package search from identifier of type %s') % type(package_identifier))

        results = self.search(domain)
        if not results and not no_results:
            if not create or name is None:
                raise ValidationError(_('Package not found for identifier %s') % str(package_identifier))
            results = self.create({'name': name})
        if len(results) > 1:
            raise ValidationError(_('Too many packages found for identifier %s') % str(package_identifier))

        return results

    def assert_not_reserved(self):
        """ Check that the content of the package is reserved, in that
            case raise an error.
        """
        self.ensure_one()
        quants = self.mapped('quant_ids') | self.mapped('children_quant_ids')
        quants.assert_not_reserved()

    def has_same_content(self, other):
        """ Compare the content of current package with the content of another package.
        """
        self.ensure_one()
        return frozenset(self._get_all_products_quantities().items()) == \
               frozenset(other._get_all_products_quantities().items())

    def mls_can_fulfil(self, mls):
        """Returns mls which the package can fulfil. If the product_qty of the
        mls is larger than in the package (i.e. in self) the mls will be split.
        """
        MoveLines = self.env["stock.move.line"]
        pack_quantities = self._get_all_products_quantities()
        can_fulfil_mls = MoveLines.browse()
        excess_mls = MoveLines.browse()
        for prod, mls_grp in mls.groupby("product_id"):
            pack_qty = pack_quantities.get(prod, 0)
            if pack_qty == 0:
                # just skip over
                continue
            fulfil_mls, excess_ml, _ = mls_grp.move_lines_for_qty(pack_qty)
            can_fulfil_mls |= fulfil_mls
            if excess_ml:
                excess_mls |= excess_ml
        return can_fulfil_mls, excess_mls

    def assert_reserved_full_package(self, move_lines):
        """ Check that a package is fully reserved at move_lines.
        """
        MoveLine = self.env['stock.move.line']

        self.ensure_one()

        pack_products = frozenset(self._get_all_products_quantities().items())
        mls_products = frozenset(move_lines._get_all_products_quantities().items())
        if pack_products != mls_products:
            # move_lines do not match the quants
            picking = move_lines.mapped('picking_id')
            picking.ensure_one()
            pack_mls = MoveLine.search([('package_id', 'child_of', self.id),
                                        ('state', 'not in', ['done', 'cancel'])
                                        ])
            other_pickings = pack_mls.mapped('picking_id') - picking
            if other_pickings:
                raise ValidationError(
                    _('The package is reserved in other pickings:') %
                    ','.join(other_pickings.mapped('name'))
                )
            # other_pickings == False means partially reserved,
            raise ValidationError(
                _('Cannot mark as done a partially reserved package.')
            )

    @api.multi
    def is_reserved(self):
        """ Whether the package is reserved for any picking.
            Expects a singleton.

        """
        self.ensure_one()

        return any([q.reserved_quantity > 0 for q in self.quant_ids])

    @api.multi
    def find_move_lines(self, aux_domain=None):
        """ Find move lines related to the package.
            Expects a singleton package.
            A further aux domain can be specified for searching
            move lines.

            Raises a ValidationError in case multiple pickings
            are associated with the found move lines.

            Returns a recordset with the move lines.

        """
        MoveLine = self.env['stock.move.line']

        domain = [('package_id', 'in', self.ids),
                  ('state', 'not in', ['done', 'cancel'])]

        if aux_domain is not None:
            domain += aux_domain

        move_lines = MoveLine.search(domain)
        picking_names = move_lines.mapped('picking_id.name')

        if len(picking_names) > 1:
            pick_names_txt = ", ".join(picking_names)
            raise ValidationError(
                _('Package %s found in multiple pickings (%s).')
                % (self.name, pick_names_txt))

        return move_lines

    def action_print_goods_slip(self):
        """
        Print label for package
        """
        Printer = self.env['print.printer']
        self.ensure_one()

        _logger.info(_("User %d requested print of goods slip "
                       "for %s") % (self.env.uid, self.name))

        spool = Printer.spool_report(docids=[self.id],
                                     report_name='udes_stock.report_package_goods_slip')
        if spool:
            return True
        else:
            raise UserError(_("Label failed to print"))

    @api.model
    def _check_allowed_package(self, values):
        wh = self.env.user.get_user_warehouse()
        if values.get('name') in wh.reserved_package_name:
            raise ValidationError(
                _('The package name %s cannot be used to create a package.' %
                  values.get('name'))
            )

    @api.model
    def create(self, values):
        self._check_allowed_package(values)
        return super(StockQuantPackage, self).create(values)

    @api.multi
    def write(self, values):
        self._check_allowed_package(values)
        return super(StockQuantPackage, self).write(values)
