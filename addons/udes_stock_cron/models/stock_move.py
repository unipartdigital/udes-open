# -*- coding: utf-8 -*-
from odoo import models, api, _

import logging
_logger = logging.getLogger(__name__)

# Map move state to the refactor stage.
STAGES = {
    "confirmed": "confirm",
    "waiting": "confirm",
    "assigned": "assign",
    "partially_available": "assign",
    "done": "validate",
}

class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_assign(self):
        """Extend _action_assign to trigger refactor action and preprocess
        location suggestions.
        n.b. _action_assign does not return anything in core Odoo, so we
        don't return any extra moves that may have been created
        by refactoring.
        """
        res = super(StockMove, self)._action_assign()

        self.exists().unreserve_partial_lines()
        assign_moves = self.exists()._action_refactor(stage="assign")

        for picking_type, moves in assign_moves.groupby("picking_type_id"):
            # location suggestions
            if picking_type.u_drop_location_preprocess:
                moves.mapped("picking_id").apply_drop_location_policy()

        assign_moves.mapped("picking_id")._reserve_full_packages()
        return res

    def unreserve_partial_lines(self):
        """Unreserve any partially reserved lines if not allowed by the picking type."""
        # Override to prevent assigning partial lines via the check
        # availability button when u_handle_partial_lines is False,
        pass

    def _unreserve_partial_lines(self):
        """Unreserve any partially reserved lines if not allowed by the picking type."""
        Move = self.env["stock.move"]

        moves_to_unreserve = Move.browse()
        partial_moves = self.filtered(lambda m: m.state == "partially_available")
        for picking_type, grouped_moves in partial_moves.groupby("picking_type_id"):
            if picking_type.u_handle_partials and not picking_type.u_handle_partial_lines:
                moves_to_unreserve += grouped_moves
        moves_to_unreserve._do_unreserve()
        return None


    def _action_refactor(self, stage=None):
        """Refactor moves in self.
        :param stage: One of confirm|assign|done, if set, filters the moves
            which will be refactored to only the state(s) that match:
                - 'confirm': confirmed, waiting
                - 'assign': assigned, partially_available
                - 'done': done
           Methods doing a refactor are expected to take a single recordset of
           moves on which they will act, and to return the recordset of
           equivalent moves after they have been transformed.
           The output moves may be identical to the input, may contain none
           of the input moves, or anywhere in between.
           The output should contain a functionally similar set of moves.
        """
        if stage is not None and stage not in STAGES.values():
            raise UserError(_("Unknown stage for move refactor: %s") % stage)
        moves = self

        if self._context.get("disable_move_refactor"):
            return moves

        rf_moves = moves.filtered(
            lambda m: m.picking_type_id and m.state not in ["draft", "cancel"]
        )
        if stage is not None:
            rf_moves = rf_moves.filtered(lambda m: STAGES[m.state] == stage)

        for picking_type, pt_moves in rf_moves.groupby("picking_type_id"):
            for stage, st_moves in pt_moves.groupby(lambda m: STAGES[m.state]):
                if stage == "confirm":
                    action = picking_type.u_post_confirm_action
                elif stage == "assign":
                    action = picking_type.u_post_assign_action
                elif stage == "validate":
                    action = picking_type.u_post_validate_action
                else:
                    continue  # Don't refactor cancel or draft moves.
                
                if action:
                    _logger.info(
                        "Refactoring %s at %s using %s: %s",
                        picking_type.name,
                        stage,
                        action,
                        st_moves.ids,
                    )
                    func = getattr(st_moves.with_context(refactor_stage=stage), "refactor_action_" + action)
                    new_moves = func()
                    if new_moves is not None:
                        moves -= st_moves
                        moves |= new_moves

        return moves

