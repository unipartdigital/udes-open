from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_assign(self):
        """Extend _action_assign to trigger full package reservation"""
        res = super(StockMove, self)._action_assign()

        self.picking_id._reserve_full_packages()
        return res
