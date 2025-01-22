from odoo import models, api

from odoo.addons.udes_common.tools import RelFieldOps
import collections


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
            # If the move lines corresponding moves have any followup moves, don't apply the push rule
            if loc_mls.move_id.move_dest_ids:
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
            "u_uom_initial_demand": quantity,
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

    def _split_pick_for_rule(self, assigned_moves, rule):
        """
        Based on the current rule, and the assigned moves, split
        the moves to a backorder, using the rule to determine the values of the new picking.

        param: assigned_moves: stock.move(x,) recordset.
        param: rule: stock.rule(x,) singleton.
        """
        StockMoveObj = self.env["stock.move"]
        res = StockMoveObj.browse()
        # Rip the moves to the operation type of the rule.
        split_pick_vals = {
            "location_id": rule.location_src_id.id,
            "location_dest_id": rule.location_id.id,
            "picking_type_id": rule.picking_type_id.id,
            "origin": assigned_moves.picking_id.origin,
        }

        # We only need to split the moves to a backorder if the picking type
        # of the rule differs from the assigned moves picking type. If it
        # is the same picking type, any post assign behaviour has already run, and
        # the move lines and moves already exist on the picking of the correct type.
        if assigned_moves.picking_type_id != rule.picking_type_id:
            split_pick = assigned_moves.picking_id._create_backorder_picking(assigned_moves, **split_pick_vals)
            # Ensure any candidate moves are merged, because the new picking type could have
            # different configuration and want to handle them differently. Get back to square 1 basically.
            split_pick.move_lines._merge_moves()
            # Update the split moves picking type to the rules picking type, to ensure
            # that when _action_assign() is called, the applicable rules get detected correctly.
            split_pick.move_lines.write(
                {
                    "picking_type_id": rule.picking_type_id.id,
                    "location_id": rule.location_src_id.id,
                }
            )
            res |= split_pick.move_lines
            # Re-trigger _action_assign() on the new split moves as they got split
            # to a new picking type and may need to run other post assign action behaviour.
            split_pick.move_lines._action_assign()

        return res

    def _split_pick_hook(self, applicable_rules):
        """
        Reserve stock from specific locations using context passing of
        the rule and remaining qty to reserve to _gather. If stock is found using
        the rule, then split its reserved lines. Track which lines get split off.
        At the end, the split off lines per rule are split into a backorder.
        """
        StockMoveObj = self.env["stock.move"]

        res = StockMoveObj.browse()
        # Allows us to build data on which moves have been split for which rules
        # which we can then split to backorder pickings after looping over all rules.
        moves_to_split_by_rule = collections.defaultdict(StockMoveObj.browse)
        # Split pick hook (different to two stage split!)
        for move in self:
            move_qty = move.product_uom_qty
            # Post assign actions could change the picking of assigned moves, so use move instead.
            picking = move.picking_id

            for rule in applicable_rules.sorted("sequence"):
                # Iterate on the rules applicable to this picking type, attempting to reserve
                # stock as per the configured rules strategy defines,
                # one by one until the stock is fully reserved or until we have run out of rules.
                if move_qty > 0:
                    assigned_moves = super(
                        StockMove,
                        move.with_context(split_pick_rule=rule, split_pick_qty=move_qty),
                    )._action_assign()
                    for assigned_move in assigned_moves:
                        # We only need to determine split characteristics if stock was assigned
                        if assigned_move.move_line_ids:
                            # Deduct the quantity we need to consider, for any lower sequenced rules
                            move_qty -= sum(assigned_move.move_line_ids.mapped("product_uom_qty"))
                            new_moves = assigned_move.split_out_move_lines(assigned_move.move_line_ids)
                            # The picking id can be cleared by split_out_move_lines, this hacks it back in.
                            new_moves.write({"picking_id": picking.id})
                            moves_to_split_by_rule[rule] |= new_moves

        # Now we have split the lines and built the information on which rule each move is related to
        # we can split those into backorders. Doing it this way prevents us from having picks with multiple
        # products (moves which cannot be _merged) backorder to several separate pickings.
        for rule, assigned_moves in moves_to_split_by_rule.items():
            res |= assigned_moves._split_pick_for_rule(assigned_moves, rule)

        return res

    def _action_assign(self):
        """
        Extend action_assign to include the two stage hook and split pick hook.
        This is done at the move level incase refactoring splits picks after assigning stock.
        This way, we don't lose any moves which need to be split to 2 stage but got refactored out.
        """
        applicable_rules = self.get_split_pick_applicable_rules()
        if applicable_rules:
            # _action_assign() _will_ be called inside here, possibly multiple times.
            res = self._split_pick_hook(applicable_rules)
        else:
            # Call super as normal
            res = super()._action_assign()

        # Two stage split hook
        for move in self:
            if move.exists() and (picking := move.picking_id):
                if picking.should_two_stage_initiate():
                    move.picking_id.initiate_two_stage_split()
        return res

    def get_split_pick_applicable_rules(self):
        # Look up stock.rule applicable to the picking type in self
        Rule = self.env["stock.rule"]
        applicable_rules = Rule.search(
            [
                ("u_run_on_assign", "=", True),
                ("u_run_on_assign_applicable_to", "in", self.picking_type_id.ids),
            ]
        )
        # We know we need to take the alternative reservation strategy if any exist.
        return applicable_rules

    def _get_available_quantity(
        self,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=False,
        allow_negative=False,
    ):
        """
        Extend to pass additional context, so that _gather can be aware of its caller location.
        This is to prevent an oddity where changing package levels due to certain configurations of picking types
        i.e user scans not being set to 'product', results in the core stock.move.line
        write calling _update_reserved_quantity due to the location_dest_id of the move line being written to
        by the package level code. The additional filtering makes the system think there is not enough stock
        when in reality there is. So this allows us to only filter in _gather when called from these locations.
        """
        self = self.with_context(filter_quants_by_rules=True)
        return super()._get_available_quantity(
            location_id,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
            allow_negative=allow_negative,
        )

    def _update_reserved_quantity(
        self,
        need,
        available_quantity,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=True,
    ):
        """
        See _get_available_quantity docstring above
        """
        self = self.with_context(filter_quants_by_rules=True)
        return super()._update_reserved_quantity(
            need,
            available_quantity,
            location_id,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
        )
