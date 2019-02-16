# -*- coding: utf-8 -*-
from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class StockMove(models.Model):

    _inherit = 'stock.move'

    u_is_privacy_wrapped = fields.Boolean(
        string='Is privacy wrapped',
        compute='_compute_privacy_wrapped',
    )

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

    def _compute_privacy_wrapped(self):
        privacy = self.env.ref('udes_stock.privacy_wrapping')
        for mv in self:
            mv.u_is_privacy_wrapped = privacy in mv.mapped(
                'sale_line_id.product_packaging')