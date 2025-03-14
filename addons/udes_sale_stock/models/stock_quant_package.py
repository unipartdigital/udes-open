from odoo import models

class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def get_sale_order(self):
        """
        Getting sale order from a package.
        """
        self.ensure_one()
        mls = self.get_move_lines_of_children([("state",  "=", "assigned")])
        sale = mls.move_id.sale_line_id.order_id
        return sale
