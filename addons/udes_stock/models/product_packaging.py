# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductPackaging(models.Model):
    _inherit = "product.packaging"

    active = fields.Boolean("Active", default=True)
