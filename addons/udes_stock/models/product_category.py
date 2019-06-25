# -*- coding: utf-8 -*-

from odoo import fields, models

class ProductCategory(models.Model):
    _inherit = 'product.category'
    _order = 'sequence asc, parent_id, id'
    sequence = fields.Integer("Sequence", default=0)
