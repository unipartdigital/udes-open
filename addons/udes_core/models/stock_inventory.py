# -*- coding: utf-8 -*-

from odoo import api, models, fields


class SotckInventory(models.Model):
    _name = 'stock.inventory'
    _inherit = 'stock.inventory'

    u_preceding_inventory_ids = fields.One2many('stock.inventory',
                                                'u_next_inventory_id',
                                                string='Preceding Inventories',
                                                readonly=True)

    u_next_inventory_id = fields.Many2one('stock.inventory',
                                          'Next inventory',
                                          readonly=True,
                                          index=True)
