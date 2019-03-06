# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)


class StockMove(models.Model):

    _inherit = 'stock.move'

    def _action_done(self):
        result = super(StockMove, self)._action_done()
        result.mapped('sale_line_id.order_id').check_delivered()

        return result

    def _action_cancel(self):

        location_customers = self.env.ref('stock.stock_location_customers')
        now_date = datetime.now()

        from_sale = self.env.context.get('from_sale', False)
        result = True
        if not from_sale:
            result = super(StockMove, self)._action_cancel()
            self.mapped('sale_line_id.order_id').check_delivered()

        def not_cancelled_filter(m):
            return m.state not in ['cancel'] \
                   and m.location_dest_id == location_customers

        lines_to_cancel = self.filtered(
            lambda m: m.location_dest_id == location_customers) \
            .mapped('sale_line_id').filtered(
            lambda s: len(s.move_ids.filtered(not_cancelled_filter)) == 0)
        lines_to_cancel.write({'is_cancelled': True,
                               'cancel_date': fields.Datetime.to_string(now_date)})
        lines_to_cancel.mapped('order_id').check_state_cancelled()

        return result
