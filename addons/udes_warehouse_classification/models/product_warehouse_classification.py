# -*- coding: utf-8 -*-

from odoo import models, fields


class ProductWarehouseClassification(models.Model):
    _name = "product.warehouse.classification"
    _description = "Information used for messaging about product qualities."
    _order = "sequence, name"

    name = fields.Char()
    alert_message = fields.Char(
        string="Alert Message", help="Message to be displayed when alerting.",
    )
    report_message = fields.Char(
        string="Report Message", help="Message to be displayed when attaching to report.",
    )
    picking_type_ids = fields.Many2many(
        comodel_name="stock.picking.type",
        string="Picking Types",
        help="Picking types which are concerned with classification",
    )
    report_template_ids = fields.Many2many(
        comodel_name="ir.actions.report",
        string="Report Types",
        help="Record templates for which the report message should be included when printing.",
    )
    sequence = fields.Integer(
        string="Sequence", default=1, help="Allows for ordering classifications."
    )
    show_when = fields.Char(
        help="A string to dictate at which actions/events the message is shown."
    )
