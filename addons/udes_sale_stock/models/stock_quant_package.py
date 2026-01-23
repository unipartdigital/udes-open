from odoo import models


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def get_sale_order(self, states=None):
        """
        Getting sale order from a package.

        When is a unique package, example parcel packages will check states assigned or done,
        otherwise only assigned move lines.
        """
        self.ensure_one()
        move_line_states = ["assigned"]
        if states:
            move_line_states += states
        mls = self.get_move_lines_of_children([("state", "in", move_line_states)])

        sale = mls.move_id.sale_line_id.order_id
        return sale
