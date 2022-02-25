from odoo import models
from collections import defaultdict


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_all_products_quantities(self):
        """This function computes the different product quantities for the given move_lines"""
        # TODO: Issue 962, make this function work with different UoMs
        res = defaultdict(int)
        for move_line in self:
            res[move_line.product_id] += move_line.product_uom_qty
        return res
