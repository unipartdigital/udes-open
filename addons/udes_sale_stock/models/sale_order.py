# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Rename states
    state = fields.Selection(selection_add=[
        ('sale', 'In Progress'),
        ('done', 'Done'),
    ])

    picking_ids = fields.One2many('stock.picking',
                                  compute="_compute_picking_ids_by_line")

    @api.depends('order_line.move_ids.picking_id')
    def _compute_picking_ids_by_line(self):
        for order in self:
            order.picking_ids = order.mapped(
                'order_line.move_ids.picking_id')

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
