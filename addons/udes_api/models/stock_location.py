# -*- coding: utf-8 -*-

from odoo import models 


class StockLocation(models.Model):
    _inherit = 'stock.location'

    def _prepare_info(self, extended=False, **kwargs):
        """
            Prepares the following extra info of the location in self
            when extended paramameter is True:
            - u_blocked: boolean
            - u_blocked_reason: string
        """
        info = super(StockLocation, self)._prepare_info(**kwargs)
        if extended:
            info['u_blocked'] = self.u_blocked
            info['u_blocked_reason'] = self.u_blocked_reason

        return info
