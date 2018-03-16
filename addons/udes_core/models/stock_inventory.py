# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class StockInventory(models.Model):
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

    @api.multi
    def action_done(self):
        """
        Extends the parent method by ensuring that there are no
        incomplete preceding inventories.

        Raises a ValidationError otherwise.
        """
        for prec in self.u_preceding_inventory_ids:
            if prec.state != 'done':
                raise ValidationError(
                    _('There are undone preceding inventories.'))

        return super(StockInventory, self).action_done()
