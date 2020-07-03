# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


# Map move state to the refactor stage.
U_STOCK_REFACTOR_STAGES = {
    "confirmed": "confirm",
    "waiting": "confirm",
    "assigned": "assign",
    "partially_available": "assign",
    "done": "validate",
}


class StockMove(models.Model):
    _inherit = "stock.move"

    def compute_grouping_key(self):
        """Compute the grouping key from the picking type move key format"""
        # TODO MTC: This can be refactored and abstracted at some point with
        # this with the equivalent for move_line_key
        # we need to think of how we want to do it

        # The environment must include {'compute_key': True}
        # to allow the keys to be computed.
        if not self.env.context.get("compute_key", False):
            return
        for move in self:
            move_vals = {
                field_name: move[field_name]
                for field_name in move._fields.keys()
                if field_name != "u_grouping_key"
            }

            format_str = move.picking_id.picking_type_id.u_move_key_format

            if format_str:
                move.u_grouping_key = format_str.format(**move_vals)
            else:
                move.u_grouping_key = None

    u_grouping_key = fields.Char("Key", compute="compute_grouping_key")

    def action_refactor(self):
        """
        Refactor all the moves in self. May result in the moves being changed
        and/or their associated pickings being deleted.
        """
        self._action_refactor()
        return True

    def _action_refactor(self, stage=None):
        """
        Refactor moves in self.
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
        if stage is not None and stage not in U_STOCK_REFACTOR_STAGES.values():
            raise UserError(_("Unknown stage for move refactor: %s") % stage)
        moves = self

        if self.env.context.get("disable_move_refactor"):
            return moves

        rf_moves = moves.filtered(
            lambda m: m.picking_type_id and m.state not in ["draft", "cancel"]
        )

        if stage is not None:
            rf_moves = rf_moves.filtered(lambda m: U_STOCK_REFACTOR_STAGES[m.state] == stage)

        for picking_type, pt_moves in rf_moves.groupby("picking_type_id"):
            for stage, st_moves in pt_moves.groupby(lambda m: U_STOCK_REFACTOR_STAGES[m.state]):
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
                    func = getattr(st_moves, "refactor_action_" + action)
                    new_moves = func()
                    if new_moves is not None:
                        moves -= st_moves
                        moves |= new_moves

        return moves

    def _action_confirm(self, *args, **kwargs):
        """
        Extend _action_confirm to trigger refactor action.

        Odoos move._action_confirm returns all the moves passed in to it, after
        merging any it can. In places the return value is used to immediately
        assign, so any created moves should be returned.

        However, in stock.move._split() in Odoo core, _action_confirm is
        called on a single move and it expects a single move to be returned
        (will error out if not). Therefore the refactor at confirm should avoid
        splitting/creating moves. Luckily this is unlikely to be an issue as
        it makes little sense to split moves at this stage, before they have
        stock reserved against them.
        """
        res = super(StockMove, self)._action_confirm(*args, **kwargs)
        post_refactor_moves = res.exists()._action_refactor(stage="confirm")

        if post_refactor_moves != res:
            raise UserError(
                _(
                    "Post confirm refactor has created or destroyed "
                    "moves, which could break things if you have the "
                    "MRP module installed"
                )
            )
        return res

    def _action_assign(self):
        """
        Extend _action_assign to trigger refactor action.
        n.b. _action_assign does not return anything in core Odoo, so we
        don't return any extra moves that may have been created
        by refactoring.
        """
        res = super(StockMove, self)._action_assign()

        self.exists()._action_refactor(stage="assign")
        return res

    def _action_done(self, cancel_backorder=False):
        """
        Extend _action_done to trigger refactor action, and push from drop

        Odoo returns completed moves.
        Therefore we will keep track of moves created by the refactor and
        return them as part of the set of completed moves.
        """
        done_moves = super(StockMove, self)._action_done()

        post_refactor_done_moves = done_moves.exists()._action_refactor(stage="validate")
        return post_refactor_done_moves

    def group_by_key(self):
        """Check each picking type has a move key format set and return the groupby"""

        # TODO MTC: This can be refactored and abstracted at some point with
        # this with the equivalent for move_line_key
        # we need to think of how we want to do it

        if any(pt.u_move_key_format is False for pt in self.picking_id.picking_type_id):
            raise UserError(
                _("Cannot group moves when their picking type has no grouping key set.")
            )

        # force recompute on u_grouping_key so we have an up-to-date key:
        return self.with_context(compute_key=True).groupby(lambda ml: ml.u_grouping_key)

    def _prepare_extra_info_for_new_picking_for_group(self, pickings, moves):
        """
        Given the group of moves to refactor and its related pickings,
        prepare the extra info for the new pickings that might be created
        for the group of moves.
        Fields with more than one value are going to be ignored.
        """
        values = {}

        origins = list(set(pickings.mapped("origin")))
        if len(origins) == 1:
            values["origin"] = origins[0]

        partners = pickings.partner_id
        if len(partners) == 1:
            values["partner_id"] = partners.id

        dates_done = list(set(moves.mapped("date")))
        if len(dates_done) == 1:
            values["date_done"] = dates_done[0]

        return values

    def refactor_action_group_by_move_key(self):
        """
        group the moves by the splitting criteria
        for each resulting group of stock.moves:
            create a new picking
            attach the stock.moves to the new picking.
        """
        picking_type = self.picking_type_id
        picking_type.ensure_one()

        if not picking_type.u_move_key_format:
            return

        return self.refactor_by_move_groups(self.group_by_key())

    def refactor_by_move_groups(self, groups):
        """
        Takes an iterator which produces key, move_group and moves
        move_group into it's own picking
        """
        Picking = self.env["stock.picking"]

        pickings = self.picking_id

        for key, move_group in groups:

            if len(move_group.location_id) > 1 or len(move_group.location_dest_id) > 1:
                raise UserError(
                    _(
                        "Move grouping has generated a group of"
                        "moves that has more than one source or "
                        'destination location. Aborting. key: "%s", '
                        'location_ids: "%s", location_dest_ids: "%s"'
                        ""
                    )
                    % (key, move_group.location_id, move_group.location_dest_id)
                )

            values = self._prepare_extra_info_for_new_picking_for_group(
                move_group.picking_id, move_group
            )

            Picking._new_picking_for_group(key, move_group, **values)

        empty_picks = pickings.filtered(lambda p: len(p.move_lines) == 0)
        if empty_picks:
            _logger.info(_("Marking empty picks after splitting for clean up."))
            empty_picks.write({"u_mark": False, "is_locked": True})

        return self

    def refactor_action_group_by_move_line_key(self):
        """
        group the move lines by the splitting criteria
        for each resulting group of stock.move.lines:
            create a new picking
            split any stock.move records that are only partially covered by the
                group of stock.moves
            attach the stock.moves and stock.move.lines to the new picking.
        """
        picking_type = self.mapped("picking_type_id")
        picking_type.ensure_one()

        if not picking_type.u_move_line_key_format:
            return

        move_lines_by_key = self.mapped("move_line_ids").group_by_key()

        return self.refactor_by_move_line_groups(move_lines_by_key.items())

    def refactor_by_move_line_groups(self, groups):
        """ 
        Takes an iterator which produces key, ml_group and moves ml_group
        into it's own picking
        """
        Move = self.env["stock.move"]
        Picking = self.env["stock.picking"]

        pickings = self.mapped("picking_id")

        result_moves = Move.browse()

        for key, ml_group in groups:
            touched_moves = ml_group.mapped("move_id")

            if (
                len(touched_moves.mapped("location_id")) > 1
                or len(touched_moves.mapped("location_dest_id")) > 1
            ):
                raise UserError(
                    _(
                        "Move Line grouping has generated a group of moves that "
                        "has more than one source or destination location. "
                        'Aborting. key: "%s", location_ids: "%s", '
                        'location_dest_ids: "%s"'
                    )
                    % (
                        key,
                        touched_moves.mapped("location_id"),
                        touched_moves.mapped("location_dest_id"),
                    )
                )

            group_moves = Move.browse()
            group_pickings = Picking.browse()
            for move in touched_moves:
                group_pickings |= move.picking_id
                move_lines = ml_group.filtered(lambda l: l.move_id == move)

                if move_lines != move.move_line_ids:
                    # The move is not entirely contained by the move lines
                    # for this grouping. Need to split the move.
                    group_moves |= move.split_out_move_lines(move_lines)
                else:
                    group_moves |= move

            values = self._prepare_extra_info_for_new_picking_for_group(group_pickings, group_moves)

            Picking._new_picking_for_group(key, group_moves, **values)
            result_moves |= group_moves

        empty_picks = pickings.filtered(lambda p: len(p.move_lines) == 0)
        if empty_picks:
            _logger.info(_("Marking empty picks after splitting for clean up."))
            empty_picks.write({"u_mark": False, "is_locked": True})

        return result_moves

    def refactor_action_batch_pickings_by_date_priority(self):
        """Batch pickings by date and priority."""
        self._refactor_action_batch_pickings_by(
            lambda picking: (picking.scheduled_date.strftime("%Y-%m-%d"), picking.priority)
        )

    def refactor_action_batch_pickings_by_date(self):
        """Batch pickings by date."""
        self._refactor_action_batch_pickings_by(
            lambda picking: (picking.scheduled_date.strftime("%Y-%m-%d"))
        )

    def _refactor_action_batch_pickings_by(self, by_key):
        """
        Group picks in batches.

        Move the pickings of the moves in this StockMove into draft batches grouped by a
        given key.

        Args:
            by_key (function): The function to generate the key to group pickings by.
                Should return a :obj:`tuple`.
        """
        PickingBatch = self.env["stock.picking.batch"]

        # Find existing draft batches.
        picking_types = self.mapped("picking_type_id")
        batches = PickingBatch.search(
            [("state", "=", "draft"), ("picking_type_ids", "in", picking_types.ids)]
        )
        batches.mapped("picking_ids")

        # Index coherent batches by key.
        batches_by_key = {}
        for batch in batches:
            pickings = batch.mapped("picking_ids")
            keys = set(by_key(picking) for picking in pickings)
            if len(keys) == 1:
                batches_by_key[next(iter(keys))] = batch

        # Add to a batch using by_key.
        for picking in self.mapped("picking_id"):
            # Identify existing batch or create new batch.
            key = by_key(picking)
            batch = batches_by_key.get(key)
            if not batch:
                batch = PickingBatch.create({})
                batches_by_key[key] = batch

            # Associate picking to the batch.
            picking.write({"batch_id": batch.id})

