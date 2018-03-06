# -*- coding: utf-8 -*-

from odoo import models, _
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

        info = {"id": self.id,
                "name": self.name,
               }

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
        if  len(results) > 1:
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

    def assert_reserved_full_package(self, picking):
        """ Check that a package is fully reserved for a picking."""
        MoveLine = self.env['stock.move.line']

        self.ensure_one()

        move_lines = picking.mapped('move_line_ids').filtered(lambda ml: ml.package_id == self)
        pack_products = frozenset(self._get_all_products_quantities().items())
        mls_products = frozenset(move_lines._get_all_products_quantities().items())
        if pack_products != mls_products:
            # move_lines do not match the quants
            #picking = move_lines.mapped('picking_id')
            #picking.ensure_one()
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
            """
            # therefore reserve the remaining quantities
            # TODO: this code can be used for whole package reservation
            quants = self._get_contained_quants()
            remaining_qtys = quants.group_quantity_by_product(only_available=True)
            picking.with_context(
                quant_ids=quants.ids)._create_moves(remaining_qtys,
                                                   confirm=True,
                                                   assign=True)
            move_lines = picking.mapped('move_line_ids').filtered(lambda ml: ml.package_id == self)
            """
        #return move_lines

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
