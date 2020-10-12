# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    u_product_warehouse_classification_ids = fields.Many2many(
        comodel_name="product.warehouse.classification",
        string="product_warehouse_classification_ids",
        help="Classifications on products used for messaging purposes.",
    )

    # def _get_classification_reports(self, picking):
    #     """Find product classifications needed for a given report"""
    #     return self.mapped("u_product_warehouse_classification_ids.report_template_ids").
