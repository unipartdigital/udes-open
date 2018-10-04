# -*- coding: utf-8 -*-

from odoo import fields, models

class ProductCategory(models.Model):
    _inherit = 'product.category'
    _order = 'parent_id, id'