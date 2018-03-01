# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def add_unexpected_parts(self, product_quantities):
        """ Extend function to check if the picking_type of the picking
            is allowed to overreceive, otherwise raise an error.
        """
        Product = self.env['product.product']
        self.ensure_one()

        if self.picking_type_id.u_over_receive:
            new_move_lines = super(StockPicking, self).add_unexpected_parts(product_quantities)
        else:
            overreceived_qtys = ["%s: %s" % (Product.get_product(id).name, qty)
                                 for id,qty in product_quantities.items()]
            raise ValidationError(
                    _("We are not expecting these extra quantities of"
                    " these parts:\n%s\nPlease either receive the right"
                    " amount and move the rest to probres, or if they"
                    " cannot be split, move all to probres.") %
                    '\n'.join(overreceived_qtys))

        return new_move_lines

    def _get_package_search_domain(self, package):
        """ Override to handle multiple levels of packages
        """
        return ['|', ('move_line_ids.package_id', 'child_of', package.id),
                '|', ('move_line_ids.result_package_id', 'child_of', package.id),
                     ('move_line_ids.u_result_parent_package_id', '=', package.id)]

    def is_compatible_package(self, package_name):
        """ The package with name package_name is compatible
            with the picking in self if:
            - The package does not exist
            - The package is not in stock
            - The package has not been used in any other picking
        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']

        self.ensure_one()
        self.assert_valid_state()

        res = True
        pickings = Picking.get_pickings(package_name=package_name)
        if len(pickings) == 0:
            package = Package.get_package(package_name, no_results=True)
            if package and package.quant_ids or package.children_ids:
                # the package exists and it contains stock or other packages
                res = False
        elif len(pickings) > 1 or (len(pickings) == 1 and self != pickings):
            # the package has been used
            res = False

        return res

    def update_picking(self, expected_package_name=None, **kwargs):
        """ Extend update_picking with a new parameter expected_package_name
            to be used during swapping packages
            TODO: finish implement and add parameter at README
        """
        # extra_context = {}

        kwargs.update({'real_time_update': self.picking_type_id.u_validate_real_time})
        if expected_package_name:
            # extra_context['expected_package'] = expected_package_name
            res = super(StockPicking, self).with_context(expected_package=expected_package_name).update_picking(**kwargs)
        else:
            res = super(StockPicking, self).update_picking(**kwargs)

        return res
        #return super(StockPicking, self).with_context(**extra_context).update_picking(**kwargs)

    def handle_swap(self, package):
        """ Mark package as done Swap expected package for package.
            that is not in the picking nor int its wave.
            Requires a context variable expected_package with the name
            of the package we want to swap with package
        """
        Package = self.env['stock.quant.package']

        self.ensure_one()

        # TODO: not handling swap packages yet
        raise ValidationError(
                _('Package %s not found in the operations of %s') %
                (package, self.name))

        allow_swap = self.picking_type_id.u_allow_swapping_packages
        if not allow_swap:
            raise ValidationError(
                    _('Package %s not found in the operations of %s') %
                    (package, self.name))

        expected_package = self.env.context.get('expected_package')
        if not expected_package:
            raise ValidationError(
                    _("Expected package to scan missing."))

        expected_package = Package.get_package(expected_package_name)
        exp_pack_mls = self.move_line_ids.filtered(lambda ml: ml.package_id == expected_package)
        if not exp_pack_mls:
            raise ValidationError(
                    _("Expected package cannot be found in picking %s") %
                    self.name)

        # at this point package is not in self, expected_package
        # it is in self

        # 1) check they have the same content

        # 1.1) check same wave
        # 1.2) if not reserved or in another picking of the same picking type
        #      call _swap_package()

        move_lines = self._swap_package(package)

        return move_lines

    def _swap_package(self):
        """ Performs the swap
        """
        pass
