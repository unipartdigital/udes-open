# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.addons.udes_stock.models import common

class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Add index to origin as this field is frequently used in searches
    origin = fields.Char(string='Source Document', 
                         help="Reference of the document that generated this sales order request.", 
                         index=True)

    # Rename states
    state = fields.Selection(selection_add=[
        ('sale', 'In Progress'),
        ('done', 'Done'),
    ])

    picking_ids = fields.One2many('stock.picking', inverse_name=None,
                                  compute="_compute_picking_ids_by_line")

    priority = fields.Selection(
        selection=common.PRIORITIES, inverse='_set_priority',
        default='1', string='Priority', index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}
    )

    @api.depends('order_line.move_ids.picking_id')
    def _compute_picking_ids_by_line(self):
        for order in self:
            order.picking_ids = order.mapped(
                'order_line.move_ids.picking_id')

    @api.multi
    def _set_priority(self):
        for order in self:
            order.mapped('order_line.move_ids').write({
                'priority': order.priority
            })

    def check_delivered(self):
        """ Update sale orders state based on the states of their related
            pickings.
            An order is considered done or cancelled when all its pickings are
            done or cancelled respectively.
        """
        for order in self:
            done_pickings = order.picking_ids.filtered(
                    lambda ml: ml.state == 'done')
            cancel_pickings = order.picking_ids.filtered(
                    lambda ml: ml.state == 'cancel')
            if len(order.picking_ids) == len(done_pickings):
                order.action_done()
            if len(order.picking_ids) == len(cancel_pickings):
                order.with_context(from_sale=True).action_cancel()

    def action_cancel(self):
        """Override to cancel by moves instead of by pickings"""
        self.mapped('order_line.move_ids')._action_cancel()
        return self.write({'state': 'cancel'})

    def check_state_cancelled(self):
        for order in self.filtered(
                lambda o: o.state not in ['done', 'cancel', 'draft']):
            non_cancelled = order.order_line.filtered(
                lambda l: not l.is_cancelled)
            if len(non_cancelled) == 0:
                order.state = 'cancel'
