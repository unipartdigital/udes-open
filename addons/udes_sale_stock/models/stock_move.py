# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime

import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):

    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        result = super(StockMove, self)._action_done(cancel_backorder=cancel_backorder)
        result.mapped("sale_line_id.order_id").check_delivered()

        return result

    def _action_cancel(self):
        location_customers = self.env.ref("stock.stock_location_customers")
        from_sale = self.env.context.get("from_sale", False)
        result = True
        if not from_sale:
            result = super(StockMove, self)._action_cancel()
            self.mapped("sale_line_id.order_id").check_delivered()

        def not_cancelled_filter(m):
            return m.state not in ["cancel"] and m.location_dest_id == location_customers

        if not self.env.context.get("disable_sale_cancel", False):
            lines_to_cancel = (
                self.filtered(lambda m: m.location_dest_id == location_customers)
                .mapped("sale_line_id")
                .filtered(lambda s: len(s.move_ids.filtered(not_cancelled_filter)) == 0)
            )
            if lines_to_cancel:
                lines_to_cancel.action_cancel()

        return result
