"""Sale order line"""

from datetime import datetime

from odoo import api, models, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_cancelled = fields.Boolean(string='Cancelled', readonly=True,
                                  default=False, index=True)
    cancel_date = fields.Datetime(string='Cancel Date',
                                  help='Time of cancellation',
                                  readonly=True, index=True)

    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id)
        values.update({
            'priority': self.order_id.priority,
        })
        return values
