"""Sale order line"""

from odoo import api, models, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_cancelled = fields.Boolean(string='Cancelled', readonly=True, store=True,
                                  default=False, index=True,
                                  compute='_compute_is_cancelled')

    @api.depends('move_ids.state')
    def _compute_is_cancelled(self):
        location_customers = self.env.ref('stock.stock_location_customers')
        for line in self:
            # get non cancelled final moves
            not_cancelled = line.move_ids.filtered(
                lambda m: m.state not in ['cancel'] and
                          m.location_dest_id == location_customers)
            line.is_cancelled = len(not_cancelled) == 0

    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id)
        values.update({
            'priority': self.order_id.priority,
        })
        return values
