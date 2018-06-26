# -*- coding: utf-8 -*-

from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility='onchange')

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)

    # Default to being a stockable product
    type = fields.Selection(default='product')
