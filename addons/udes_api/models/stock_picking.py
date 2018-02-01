# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def update_picking(self, expected_package_name=None, **kwargs):
        """ Extend update_picking with a new parameter expected_package_name
            to be used during swapping packages
            TODO: finish implement and add parameter at README
        """
        # extra_context = {}
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
