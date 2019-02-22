"""Sale order line"""

from datetime import datetime

from odoo import api, models, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_cancelled = fields.Boolean(string='Cancelled', readonly=True, store=True,
                                  default=False, index=True,
                                  compute='_compute_is_cancelled')
    cancel_date = fields.Datetime(string='Cancel Date',
                                  help='Time of cancellation',
                                  readonly=True, index=True)

    @api.depends('move_ids.state')
    def _compute_is_cancelled(self):
        location_customers = self.env.ref('stock.stock_location_customers')
        now_date = datetime.now()

        def not_cancelled_filter(m):
            return m.state not in ['cancel'] \
                   and m.location_dest_id == location_customers

        for line in self.filtered(lambda l: not l.is_cancelled):
            if not line.move_ids:
                line.is_cancelled = False
                continue

            # The sale order line will be flagged as cancelled based
            # on whether it has finalized moves that were not cancelled
            not_cancelled_moves = line.move_ids.filtered(not_cancelled_filter)
            line.is_cancelled = len(not_cancelled_moves) == 0

            if line.is_cancelled:
                line.write({'cancel_date': fields.Datetime.to_string(now_date)})

    @api.onchange('is_cancelled')
    @api.constrains('is_cancelled')
    def compute_order_state(self):
        for order, lines in self.groupby('order_id'):
            order.check_state_cancelled()

    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id)
        values.update({
            'priority': self.order_id.priority,
        })
        return values
