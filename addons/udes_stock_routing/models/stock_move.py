from odoo import models, api

from odoo.addons.udes_common.tools import RelFieldOps


class StockMove(models.Model):
    _inherit = "stock.move"

    def push_from_drop(self):
        """
        Creates new moves for the moves that have just dropped stock in a location.
        NOTE: Uses sudo to override permissions. This is because the use case for this function
        is independent of the user permissions.
        """
        self = self.sudo()
        Move = self.env["stock.move"]
        MoveLine = self.env["stock.move.line"]
        Push = self.env["stock.rule"]

        done_moves = self.filtered(lambda m: m.state == "done")

        # load all the move lines, grouped by location
        move_lines_by_location = done_moves.move_line_ids.groupby("location_dest_id")

        # Build mapping of push rule -> move lines to push
        move_lines_by_push = {}
        for location, loc_mls in move_lines_by_location:
            # Get the push rule that moves from the location.
            push_step = Push.get_path_from_location(location)
            if not push_step:
                continue
            if push_step not in move_lines_by_push:
                move_lines_by_push[push_step] = MoveLine.browse()
            move_lines_by_push[push_step] |= loc_mls

        created_moves = Move.browse()
        for push, move_lines in move_lines_by_push.items():
            created_moves |= self._create_moves_for_push(push, move_lines)

        confirmed_moves = created_moves._action_confirm()
        confirmed_moves._action_assign()

    def _get_push_move_vals(self, move_lines):
        """
        Create and return a dict of values from single move in self,
        used to create new move for push rule.

        Set quantity from total of move's move lines and set link to original move.
        """
        self.ensure_one()

        quantity = sum(move_lines.mapped("qty_done"))
        move_vals = {
            "product_uom_qty": quantity,
            'u_uom_initial_demand': quantity,
            "move_orig_ids": [(RelFieldOps.Replace, 0, self.ids)],
        }
        return move_vals

    @api.model
    def _create_moves_for_push(self, push, move_lines):
        """Create moves for a push rule to cover the quantity in move_lines"""
        Move = self.env["stock.move"]

        # Group mls by move so we can preserve move information.
        mls_by_move = move_lines.groupby("move_id")
        created_moves = Move.browse()
        base_vals = {
            "picking_type_id": push.picking_type_id.id,
            "location_id": push.location_src_id.id,
            "location_dest_id": push.location_id.id,
            "picking_id": None,
        }
        for move, mls in mls_by_move:
            move_vals = base_vals.copy()
            move_vals.update(move._get_push_move_vals(mls))
            created_moves |= move.copy(move_vals)
        return created_moves

    def _action_done(self, cancel_backorder=False):
        """
        Extend _action_done to push from drop.
        """
        done_moves = super()._action_done(cancel_backorder=cancel_backorder)
        done_moves.push_from_drop()
        return done_moves

    def _get_new_picking_values(self):
        """
        Extend _get_new_picking_values() to propagate the origin and partner_id fields for next "push" picking.
        """
        values = super()._get_new_picking_values()
        previous_pickings = self.move_orig_ids.picking_id
        if not values.get("origin"):
            previous_origin = list(set(previous_pickings.mapped("origin")))
            if len(previous_origin) == 1:
                values["origin"] = previous_origin[0]
        if not values.get("partner_id"):
            previous_partner = previous_pickings.partner_id
            if len(previous_partner) == 1:
                values["partner_id"] = previous_partner.id

        return values
