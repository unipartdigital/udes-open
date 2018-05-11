# -*- coding: utf-8 -*-

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def can_handle_partials(self):
        self.ensure_one()
        return self.picking_type_id.u_handle_partials
