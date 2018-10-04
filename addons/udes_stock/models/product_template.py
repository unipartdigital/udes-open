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

    u_hazardous = fields.Boolean(string="Hazardous", default=False)

    u_manufacturer_part_no = fields.Char(string="Mfr Part No", help="Manufacturer part number")

    # TODO domain child_of default category height/speed
    u_height_category_id = fields.Many2one(
        comodel_name='product.category',
        string='Product Category Height',
        help="Product category height to match with location height.",
    )
    u_speed_category_id = fields.Many2one(
        comodel_name='product.category',
        string='Product Category Speed',
        help="Product category speed to match with location speed.",
    )
