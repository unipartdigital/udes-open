# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_use_product_packaging = fields.Boolean(
        string='Use Product Packaging',
        default=False,
        help='Flag to indicate if privacy wrapping information is relevant.',
    )
