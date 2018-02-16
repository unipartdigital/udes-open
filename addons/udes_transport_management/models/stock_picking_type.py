# -*- coding: utf-8 -*-

from odoo import models, fields


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_requires_transport = fields.Boolean('Show transport management tab')

    def _prepare_info(self):
        """
            Prepares the following extra info of the picking_type in self:
            - u_allow_transport_management: boolean
        """
        info = super(StockPickingType, self)._prepare_info()
        info.update({
            'u_requires_transport': self.u_requires_transport
        })
        return info
