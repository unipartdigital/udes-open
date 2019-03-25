"""UDES Stock stock reservation wizard."""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ReserveStockPicking(models.TransientModel):
    """Responsible for reserving individual pickings."""

    _name = 'stock.reserve.stock.wizard'
    _description = 'Trigger reservation of stock from the UI'

    @api.multi
    def do_reservation(self):
        """Reserves stock for each selected pick."""
        Picking = self.env['stock.picking']
        self.ensure_one()
        picking_ids = self.env.context.get('active_ids')

        _logger.info("User %r has requested stock reservation for pickings %r",
                     self.env.uid, picking_ids)

        by_state = lambda x: x.state == 'confirmed'
        pickings = Picking.browse(picking_ids).filtered(by_state)
        for _key, group in pickings.groupby(lambda x: x.batch_id):
            reserve_batches = group.mapped('picking_type_id.u_reserve_batches')
            if all(reserve_batches):
                group.reserve_stock()
            else:
                for picking in group:
                    picking.reserve_stock()
        return
