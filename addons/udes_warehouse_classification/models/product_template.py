# -*- coding: utf-8 -*-
import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    u_product_warehouse_classification_ids = fields.Many2many(
        comodel_name="product.warehouse.classification",
        string="product_warehouse_classification_ids",
        help="Classifications on products used for messaging purposes.",
    )

    def get_classification_messages_for_report(self, report_name):
        """Find product classification messages needed for a given report"""
        if not self.mapped("u_product_warehouse_classification_ids"):
            _logger.info("Product {} has no warehouse classifications.".format(", ".join(self.mapped("name"))))
            return []
        Report = self.env["ir.actions.report"]
        report = Report._get_report_from_name(report_name)
        if not report:
            report = self.env.ref(report_name, raise_if_not_found=False)
        return (
            self.mapped("u_product_warehouse_classification_ids")
            .filtered(lambda c: report in c.report_template_ids)
            .mapped("report_message")
        )
