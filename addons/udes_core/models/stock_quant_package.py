# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def _prepare_info(self, extended=False):
        """
            Prepares the following info of the package in self:
            - id: int
            - name: string

            When extended is True also return:
            - quant_ids: [{stock.quants}]
        """
        self.ensure_one()
        location_info = self.location_id.get_info()

        info = {"id": self.id,
                "name": self.name,
                "location_id": location_info[0] if location_info else {}}

        if extended:
            info['quants'] = self.quant_ids.get_info()

        return info

    def get_info(self, extended=False):
        """ Return a list with the information of each package in self.
        """
        res = []
        for pack in self:
            res.append(pack._prepare_info(extended=extended))

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
        self.mapped('quant_ids').assert_not_reserved()

    def has_same_content(self, other):
        """ Compare the content of current package with the content of another package.
        """
        self.ensure_one()
        return frozenset(self._get_all_products_quantities().items()) == \
               frozenset(other._get_all_products_quantities().items())

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

    # TODO Fix in odoo core (copy pasted from there)
    def _get_all_products_quantities(self):
        '''This function computes the different product quantities for the given package
        '''
        # TDE CLEANME: probably to move somewhere else, like in pack op
        res = {}
        for quant in self._get_contained_quants():
            if quant.product_id not in res:
                res[quant.product_id] = 0
            res[quant.product_id] += quant.quantity
        return res

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
        self.ensure_one()
        MoveLine = self.env['stock.move.line']

        domain = [('package_id', '=', self.id),
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
