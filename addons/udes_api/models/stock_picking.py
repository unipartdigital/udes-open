# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _handle_swap(self, package):
        """ Check if package is in move_lines, if it is not check if
            packages can be swapped
        """
        self.ensure_one()

        if package not in self.move_lines.mapped('package_id.name'):
            # atm validate is only called per picking
            allow_swap = self.picking_type_id.u_allow_swapping_packages
            if allow_swap:
                move_lines = self._swap_package(package)
            else:
                raise ValidationError(
                        _('Package %s not found in the operations of %s') %
                        (package, self.name))

        return move_lines


