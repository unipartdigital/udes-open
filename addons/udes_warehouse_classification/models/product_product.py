from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def get_classification_messages_for_report(self, report_name):
        """Find product classification messages needed for a given report"""
        return self.mapped("product_tmpl_id").get_classification_messages_for_report(report_name)
