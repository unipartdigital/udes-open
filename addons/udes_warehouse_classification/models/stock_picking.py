# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_classification_messages_for_product_picking(self):
        """
        Return the product with classification messages appropriate for a picking
        """
        self.ensure_one()
        product_classifications = super()._get_classification_messages_for_product_picking()
        products = self.mapped("move_lines.product_id")
        for product in products:
            classifications = product.u_product_warehouse_classification_ids.filtered(
                lambda c: self.picking_type_id in c.picking_type_ids
            ).sorted("sequence")
            product_classifications[product.barcode] = [
                {"message": classification.alert_message} for classification in classifications
            ]
        return product_classifications
