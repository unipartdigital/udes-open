# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    u_product_warehouse_classification_ids = fields.Many2many(
        comodel_name="product.warehouse.classification",
        string="product_warehouse_classification_ids",
        help="Classifications on products used for messaging purposes.",
    )

    def get_classification_messages_for_report(self, report_name):
        """Find product classification messages needed for a given report"""
        report = self.env.ref(report_name)
        return (
            self.mapped("u_product_warehouse_classification_ids")
            .filtered(lambda c: report in c.report_template_ids)
            .mapped("report_message")
        )
