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

    def _prepare_info(self, priorities=None, fields_to_fetch=None):
        """{doc}
           Extensions:
           - u_classification_messages: list
        """.format(
            doc=super()._prepare_info.__doc__
        )
        info = super()._prepare_info(priorities=priorities, fields_to_fetch=fields_to_fetch)
        if fields_to_fetch is None or "u_classification_messages" in fields_to_fetch:
            info[
                "u_classification_messages"
            ] = self._get_classification_messages_for_product_picking()
        return info
