# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError

class ProductProduct(models.Model):
    _inherit = "product.product"

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility='onchange')
