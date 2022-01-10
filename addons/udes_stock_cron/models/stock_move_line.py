# -*- coding: utf-8 -*-
from odoo import models, fields, _
from collections import defaultdict

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def any_destination_locations_default(self):
        """Checks if all location_dest_id's are the picks default
           location_dest_id of the picking.
        """
        default_dest = self.mapped("picking_id.location_dest_id")
        default_dest.ensure_one()
        return any(ml.location_dest_id == default_dest for ml in self)
    
    def _get_all_products_quantities(self):
        """This function computes the different product quantities for the given move_lines
        """
        res = defaultdict(int)
        for move_line in self:
            res[move_line.product_id] += move_line.product_uom_qty
        return res