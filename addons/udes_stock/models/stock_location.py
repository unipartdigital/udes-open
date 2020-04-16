# -*- coding: utf-8 -*-
from odoo import fields, models

class StockLocation(models.Model):
    _name = 'stock.location'

    # Add messages to locations
    _inherit = ['stock.location', 'mail.thread']

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility='onchange')
