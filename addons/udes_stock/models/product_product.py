# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "mixin.stock.model"]

    # Allow to search via both name and barcode
    MSM_STR_DOMAIN = ("name", "barcode")

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility="onchange")
