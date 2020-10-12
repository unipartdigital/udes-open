# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_product_classfication_messages(self):
        """Find product classifications needed for a given picking"""
        return self.mapped("move_lines.product_id.u_product_warehouse_classification_ids").filtered(
            lambda c: self.picking_type_id in c.picking_type_ids
        )
