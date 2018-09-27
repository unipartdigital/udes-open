# -*- coding: utf-8 -*-
from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class StockMove(models.Model):

    _inherit = 'stock.move'

    def _action_done(self):
        result = super(StockMove, self)._action_done()
        result.mapped('sale_line_id.order_id').check_delivered()

        return result

    def _action_cancel(self):
        from_sale = self.env.context.get('from_sale', False)
        result = True
        if not from_sale:
            result = super(StockMove, self)._action_cancel()
            self.mapped('sale_line_id.order_id').check_delivered()

        return result
