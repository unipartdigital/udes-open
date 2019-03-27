from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class RefactorStockPicking(models.TransientModel):
    _name = 'stock.warehouse.orderpoint.replen.wizard'
    _description = 'Trigger replenishment of pickings from the UI'

    @api.multi
    def do_replen(self):
        Procurement = self.env['procurement.group']
        Procurement.check_order_points(True)

        return True
