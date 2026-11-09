from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_blocked_reservation_groups(self):
        """
        Extend to move the move lines in batches which are reserved atomically to
        full_reservation when blocking, adding the pickings of their batches to
        full_reservation_pickings, as the batches are reserved together
        """
        groups = super()._get_blocked_reservation_groups()
        batch_move_lines = groups["unreservable"].filtered(
            lambda ml: ml.picking_id.batch_id and ml.picking_id.picking_type_id.u_reserve_batches
        )
        groups["unreservable"] -= batch_move_lines
        groups["full_reservation"] |= batch_move_lines
        groups["full_reservation_pickings"] |= batch_move_lines.picking_id.batch_id.picking_ids
        return groups
