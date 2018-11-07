# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    u_delivery_slot_id = fields.Many2one('udes.delivery.slot',
                                         string='Delivery Slot')
