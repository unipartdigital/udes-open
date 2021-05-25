from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def get_classification_messages_for_report(self, report_name):
        """Find product classification messages needed for a given report"""
        return self.mapped("product_tmpl_id").get_classification_messages_for_report(report_name)

    def get_printable_classification_names(self, separator="", order_key="name"):
        """Return a string of the product classifications in self"""
        return self.mapped("product_tmpl_id").get_printable_classification_names(separator, order_key)
