from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class RefactorStockPicking(models.TransientModel):
    _name = 'stock.picking.refactor.wizard'
    _description = 'Trigger refactoring of pickings from the UI'

    @api.multi
    def do_refactor(self):
        Picking = self.env['stock.picking']
        self.ensure_one()
        picking_ids = self.env.context.get('active_ids')

        _logger.info("User number {UID} has requested refactoring of pickings "
                     "{PICKINGS}".format(UID=str(self.env.uid),
                                         PICKINGS=picking_ids))

        pickings = Picking.browse(picking_ids)
        res = pickings.mapped('move_lines')._action_refactor()
        pickings.unlink_empty()
        return res


class RefactorStockMove(models.TransientModel):
    _name = 'stock.move.refactor.wizard'
    _description = 'Trigger refactoring of moves from the UI'

    @api.multi
    def do_refactor(self):
        Move = self.env['stock.move']
        self.ensure_one()
        move_ids = self.env.context.get('active_ids')

        _logger.info("User number {UID} has requested refactoring of moves "
                     "{MOVES}".format(UID=str(self.env.uid),
                                      MOVES=move_ids))

        moves = Move.browse(move_ids)
        res = moves._action_refactor()
        self.mapped('picking_id').unlink_empty()
        return res

class RefactorStockPickingBatch(models.TransientModel):
    _name = 'stock.picking.batch.refactor.wizard'
    _description = 'Trigger refactoring of batches from the UI'

    @api.multi
    def do_refactor(self):
        Batch = self.env['stock.picking.batch']
        self.ensure_one()
        batch_ids = self.env.context.get('active_ids')

        _logger.info("User number {UID} has requested refactoring of batches "
                     "{BATCHES}".format(UID=str(self.env.uid),
                                      BATCHES=batch_ids))

        batches = Batch.browse(batch_ids)
        res = batches.mapped('picking_ids.move_lines')._action_refactor()
        batches.mapped('picking_ids').unlink_empty()
        return res        
