# -*- coding: utf-8 -*-

'''Print Strategy for stock picking.'''

from odoo import api, fields, models

class PrintStrategy(models.Model):
    '''Print strategies for stock picking by picking type.'''

    _name = 'udes_stock.stock.picking.print.strategy'
    _inherit = 'print.strategy'

    # the picking type to which this print strategy applies
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Picking Type',
        required=True,
    )

    @api.model
    def strategies(self, picking):
        '''Return print strategies for the picking type of `picking`.'''
        picking.ensure_one()
        return self.search([
            ('picking_type_id', '=', picking.picking_type_id.id),
        ])

    @api.multi
    def records(self, picking, report=None):
        '''Return records for printing `picking` using `report`.'''
        picking.ensure_one()
        return picking
