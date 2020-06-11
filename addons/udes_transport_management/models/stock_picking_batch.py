# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

import logging

_logger = logging.getLogger(__name__)


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    u_driver_id = fields.Many2one('res.partner', string='Driver', index=True, domain=[('is_driver', '=', True)])
    u_transporter_id = fields.Many2one('res.partner', string='Transporter', index=True, domain=[('is_transporter', '=', True)])
