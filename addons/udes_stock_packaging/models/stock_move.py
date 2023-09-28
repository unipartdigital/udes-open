from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_assign(self):
        """Extend _action_assign to trigger full package reservation"""
        res = super(StockMove, self)._action_assign()

        self.picking_id._reserve_full_packages()
        return res

    def _needs_full_product_reservation(self):
        """Overriden to return full package reservation depending on the picking type config"""
        full_reservation = super()._needs_full_product_reservation()
        return full_reservation or self.picking_type_id.u_reserve_as_packages
