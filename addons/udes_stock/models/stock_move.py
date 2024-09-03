import logging
import math

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    u_uom_initial_demand = fields.Float(
        "Initial Demand",
        digits="Product Unit of Measure",
        help="The original quantity when the move was created",
    )

    # Override product_uom_qty to change string from "Demand" to "Quantity", because of
    # how we are now tracking initial demand in u_uom_initial_demand.
    product_uom_qty = fields.Float(string="Quantity")

    @api.model
    def create(self, vals):
        """Extend create to set the initial demand to product_uom_qty if no value set"""
        if "u_uom_initial_demand" not in vals:
            vals["u_uom_initial_demand"] = vals.get("product_uom_qty")
        return super().create(vals)

    def _action_cancel(self):
        """
        Extend _action_cancel to;
        - Set move_line_ids to have a qty_done of 0
        - Include a context bypass in the super call to prevent initial demand re-setting
        - Include a hook to propagate cancellations when the picking
          type is configured with u_propagate_cancel set to True
        """
        if self.move_line_ids:  # Merging moves may assign move lines to another move and cancel this, skip those
            self.move_line_ids.write({"qty_done": 0})
        # Pull out old move_dest_ids as these _can_ be removed upon cancellation
        old_dest_ids = {m.id: m.move_dest_ids for m in self}
        res = super(
            StockMove, self.with_context({"bypass_set_qty_to_initial_demand": True})
        )._action_cancel()
        for move in self:
            if move.picking_type_id.u_propagate_cancel:
                move.propagate_cancellation_to_next_picks(old_dest_ids.get(move.id))

        return res

    def _do_unreserve(self):
        """
        Extend _do_unreserve to remove extra quantities added to initial_demand when
        unreserving a package.
        """
        res = super()._do_unreserve()
        # Allow bypassing the qty reset with context
        if not self.env.context.get("bypass_set_qty_to_initial_demand"):
            for move in self.filtered(lambda mv: mv._needs_full_product_reservation()):
                move.write({"product_uom_qty": move.u_uom_initial_demand})
        return res

    def _needs_full_product_reservation(self):
        """
        If picking type config is set up to full reserve the move than write product qty with
        initial demand quantity. Method will be extended in other modules.
        """
        self.ensure_one()
        return False

    def _prepare_move_line(self, move, uom_qty, uom_id=None, **kwargs):
        """
        Return a dict of the move line details to be used later in creation of the move line(s).
        Note that we pass the uom_qty here instead of qty.

        :args:
            - move: move object to be assigned to the move line
            - uom_qty: float value for uom quantity of the move line generated
            - uom_id: Pass a UoM record id incase you want the move UoM to differ to the products

        :returns:
            vals: dict
        """
        move.ensure_one()
        vals = {
            "product_id": move.product_id.id,
            "product_uom_id": uom_id or move.product_uom.id,
            "product_uom_qty": uom_qty,
            "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
            "move_id": move.id,
            "picking_id": move.picking_id.id,
        }
        vals.update(kwargs)

        return vals

    def _prepare_move_lines(self, moves_info, **kwargs):
        """
        Return a list of the move line details to be used later in creation of the move line(s).
        The purpose of this is to allow for multiple move lines to be created at once.

        :args:
            - moves_info: dict of move, uom quantity float value

        :returns:
            move_line_values: list(dict)

        """
        move_line_values = []

        for move, qty in moves_info.items():
            vals = self._prepare_move_line(move, qty, **kwargs)
            move_line_values.append(vals)

        return move_line_values

    @api.model
    def _create_move_line(self, move_line_values):
        """
        Create and return move line(s) for the given move_line_values.
        Should be used in conjunction with _prepare_move_line to obtain move_values

        :args:
            - move_line_values: list of dictionary values (or single dictionary) to create move line

        :returns:
            - move line
        """
        MoveLine = self.env["stock.move.line"]

        return MoveLine.create(move_line_values)

    def _unreserve_initial_demand(self, new_move):
        """
        Override the odoo core hook to keep the old move lines without unreserving them.

        Writing the state to the new move which will keep moves in same state and won't be needed to
        reserve them again. Recomputing new move state at the end.
        """
        self.ensure_one()
        self.move_line_ids.filtered(lambda ml: ml.qty_done == 0.0).write({"move_id": new_move.id})
        new_move.write({"state": self.state})
        new_move._recompute_state()

    def propagate_cancellation_to_next_picks(self, old_dest_ids):
        """
        Propagate cancelled qtys to move_dest_ids.
        If a full qty match is found, cancel that move - calling this function for that move
        If a part qty match is found, decrement the qty from the move, and continue down the chain

        `propagate_cancel` on `stock.rule` could be used, however it is not visible on `Push` rules
        and does not appear to propagate partial cancellations.

        :param: old_dest_ids: stock.move(x) recordset(s), fallback if no move_dest_ids in self.
                              Can be emptyset
        """
        StockMove = self.env["stock.move"].browse()
        next_moves = self.move_dest_ids
        if not next_moves:
            # NB: This handles a symptom of Issue #2771
            next_moves = old_dest_ids
        qty = self.product_uom_qty
        while next_moves:
            fully_matched_move = next_moves.filtered(lambda m: m.product_uom_qty == qty)
            for move in fully_matched_move:
                move._action_cancel()
                # Recurse via action_cancel, we don't need to continue through the chain here.
                next_moves = StockMove
            else:
                next_moves_todo = next_moves
                next_moves = StockMove  # Clear this as we potentially rebuild inside the loop
                for move in next_moves_todo:  # Iterate on the non-cleared set
                    if move.product_uom_qty > qty:
                        move.product_uom_qty -= qty
                        # Recursing inside here is only necessary for part cancellations
                        if move.picking_type_id.u_propagate_cancel:
                            next_moves |= move.move_dest_ids
                    else:  # move qty is less, as there was no fully_matched_move
                        move._action_cancel()

    def split_out_move_lines(self, move_lines, **kwargs):
        """Split sufficient quantity from self to cover move_lines, and
        attach move_lines to the new move. Return the move that now holds all
        of move_lines.
        If self is completely covered by move_lines, it will be removed from
        its picking and returned.
        Included code for splitting out partially done ones.
        Preconditions: self is a single move,
                       all moves_line are attached to self
        :return: The (possibly new) move that covers all of move_lines,
                 not currently attached to any picking.

            Note: not using stock.move._split() since we want better handling of
                move_orig_ids and move_dest_ids
            Note: in 14.0 core stock.move._split() no longer returns the move id
                and instead returns the vals to create a move
        """
        self.ensure_one()
        if not all(ml.move_id == self for ml in move_lines):
            raise ValueError(_("Cannot split move lines from a move they are not part of."))
        if (
            move_lines == self.move_line_ids
            and not self.move_orig_ids.get_incomplete_moves()
            and not self.state == "partially_available"
        ):
            new_move = self
            new_move.write({"picking_id": None})
        else:
            done_mls = move_lines.filtered(lambda ml: ml.state == "done")
            new_move_qty = (
                sum(move_lines.mapped("qty_done"))
                if done_mls
                else sum(move_lines.mapped("product_qty"))
            )
            remaining_move_qty = self.product_uom_qty - new_move_qty
            new_move = self._create_split_move(
                move_lines, remaining_move_qty, new_move_qty, **kwargs
            )

        return new_move

    def get_incomplete_moves(self):
        """
        Return the set of incomplete moves from self.
        We define incomplete as a move that is not in state `done` or `cancel`.
        """
        return self.filtered(lambda mv: mv.state not in ("done", "cancel"))

    def get_moves_with_quantity_todo(self):
        """
        Return the set of moves with outstanding quantities in self.
        Excludes cancelled moves.
        """
        return self.filtered(lambda m: m.state != "cancel" and m.quantity_done < m.product_uom_qty)

    def get_uncovered_moves(self, mls):
        """
        Return the moves in self not covered by mls regardless of the mls state.
        Here we define uncovered as:
            move product_uom_qty > sum relevant mls product_uom_qty
        Namely, all the mls passed cannot fulfil the associated move.
        """
        Move = self.env["stock.move"]
        # Pre-cache mls
        self.move_line_ids

        uncovered_moves = Move.browse()
        for move in self:
            keep_mls = move.move_line_ids & mls
            if move.product_uom_qty > sum(keep_mls.mapped("product_uom_qty")):
                uncovered_moves |= move
        return uncovered_moves

    def check_move_lines_not_partially_fulfilled(self):
        """
        Check that any of the move lines in self are not partially completed,
        i.e there are no mls where 0 < qty_done < product_uom_qty.
        """
        mls = self.move_line_ids
        if mls.get_lines_partially_complete():
            raise ValidationError(
                _("There are partially fulfilled move lines in picking %s!") % self.picking_id.name
            )

    def split_out_move(self, mls_to_keep=None, **kwargs):
        """
        Split the move in self.
            * mls is None: Retain all mls with qty_done == product_uom_qty in self
        and move all other work into the new move.
            * mls is not None: Retain mls_to_keep in self, and remove all other work,
        into the new move.

        :kwargs:
            - mls_to_keep: The move lines to keep in self, if None use all mls with
            qty_done == product_uom_qty.
        :returns:
            - If a move has nothing complete, return self, detached from the pickng
            - If a move has everything complete, return an empty record set
            - If the move is partially complete, return the new move with the incomplete
            work.
        :raises: An error if any move lines attached to self are partially complete.
        :raises: An error if any move lines being moved are done, and any move line reatined
            is incomplete.

        WARNING: Assumes that if a move is over picked (product_uom_qty < quantity_done) then
        any adjustment to that move has been done before hand.
        """
        Move = self.env["stock.move"]
        self.ensure_one()

        mls = self.move_line_ids

        # Raise an error if any of the move lines are partially fulfilled
        self.check_move_lines_not_partially_fulfilled()

        # Check if there is something to split
        #   * If the quantity_done on the move is zero, and no move lines are passed,
        #   there is no need to split up the move.
        #   * If the mls_to_keep cover the whole move
        # We just return self, but with it kicked out of the picking.
        if (self.quantity_done == 0 and not mls_to_keep) or (
            mls_to_keep and sum(mls_to_keep.mapped("product_uom_qty")) == self.product_uom_qty
        ):
            # Clear the picking information
            self.write({"picking_id": False})
            if mls:
                mls.write({"picking_id": False})
            return self

        # Get the mls_to_keep when not specified in the call
        if mls_to_keep is None:
            mls_to_keep = mls.get_lines_done()

        mls_to_move = mls - mls_to_keep
        # Ensure that if any mls_to_move are done, all mls_to_keep are as well!
        if mls_to_move.get_lines_done() and mls_to_keep.get_lines_incomplete():
            raise ValidationError(
                _(
                    "You cannot move done move lines into a new move, if the existing move has incomplete lines"
                )
            )

        # Return an empty record set if the move has been fulfilled for now.
        if self.product_uom_qty == sum(mls_to_keep.mapped("qty_done")):
            return Move.browse()

        # Split the move
        # Manually create a new one and move the remaining quantity into it,
        # along with previously created move lines with qty_done == 0.
        total_move_qty = self.product_uom_qty
        current_move_qty = sum(mls_to_keep.mapped("product_uom_qty"))
        new_move_qty = total_move_qty - current_move_qty

        return self._create_split_move(mls_to_move, current_move_qty, new_move_qty, **kwargs)

    def _create_split_move(self, move_lines, remaining_qty, new_move_qty, **kwargs):
        """
        Logic to split a move into two.

        :args:
            move_lines: the move lines to be placed into the new move
            new_move_qty: the new move quantity (not equal to move line
            quantity since partially available moves could occur.)
        :returns:
            - The new move
        """
        default_values = {
            "picking_id": False,
            "move_line_ids": [],
            "move_orig_ids": [],
            # move_dest_ids not copied by default
            # WS-MPS: this might need to be refined like move_orig_ids
            "move_dest_ids": [(6, 0, self.move_dest_ids.ids)],
            "product_uom_qty": new_move_qty,
            "state": self.state,
        }
        default_values.update(kwargs)
        new_move = self.copy(default_values)

        # Update the moved move lines with the new move, and no picking id
        move_lines.write({"move_id": new_move.id, "picking_id": None})

        # Adding context variables to avoid any change to be propagated to
        # the following moves and do not unreserve any quant related to the
        # move being split.
        context_vars = {
            "bypass_reservation_update": True,
            "do_not_propagate": True,
            "do_not_unreserve": True,
        }
        self.with_context(**context_vars).write({"product_uom_qty": remaining_qty})

        # When not complete, splitting a move may change its state,
        # so recompute
        incomplete_moves = (self | new_move).get_incomplete_moves()
        incomplete_moves._recompute_state()

        move_lines.write({"state": new_move.state})

        if self.move_orig_ids:
            # Update the current and new move original move ids.
            (self | new_move).update_orig_ids(self.move_orig_ids)

        return new_move

    def _clean_merged(self):
        """
        Remove related moves of the moves that will be cancelled and unlinked after to not
        propagate cancellation on the related moves.

        Remove related moves if method is triggered by refactoring.
        """
        super()._clean_merged()
        if self._context.get("remove_related_moves"):
            self.write({
                "move_dest_ids": [(5,)],
                "move_orig_ids": [(5,)],
            })

    def _make_mls_comparison_lambda(self, move_line):
        """
        This makes the lambda for checking the move_line against move_origin_ids
        This can be overridden in other modules if desired.
        If no matching is made, it defaults to a matching on the dest location
        and product id. This is not very robust and can lead to over-matching.

        The saving grace of the default behaviour is that it is not very common.
        Normally, if not lot tracked, there are packages/pallets, and if not there
        are procurement groups which block the merging of moves/pickings.

        :args:
            - move_line to match self with
        :returns:
            - lambda expression for matching
        """
        lot_name = move_line.lot_id.name or move_line.lot_name
        package = move_line.package_id

        if lot_name and package:
            return lambda ml: ml.result_package_id == package and (
                ml.lot_name == lot_name or ml.lot_id.name == lot_name
            )
        elif lot_name:
            return lambda ml: ml.lot_name == lot_name or ml.lot_id.name == lot_name
        elif package:
            return lambda ml: ml.result_package_id == package

        return (
            lambda ml: ml.location_dest_id == move_line.location_id
            and ml.product_id == move_line.product_id
        )

    def update_orig_ids(self, origin_moves):
        """
        Updates the move_orig_ids for all moves in self.

        For all move lines in each move, match the move line
        to one from the original id, if any match attach those moves as well.

        Using _make_mls_comparison_lambda does cause over matching if they are not identifiable
        this is left because of the issue of untraceability should be avoided.

        For any unmatched quantity of moves, attempt to match this up via a move key made up
        of the product and quantity. This helps to ensure the chain is correct when a picking is
        backordered and the earlier picking in the chain is also waiting on a backorder
        to be completed.

        Examples can be found in test_stock_move.py

        NOTE: If there are performance issues with mapped and computing the over matching
        consider moving the warning to the _make_mls_comparison_lambda or disable the checks
        for live and have it as a UAT testing commit.
        """
        Move = self.env["stock.move"]

        self.picking_id.ensure_one()
        origin_mls = origin_moves.move_line_ids

        used_origin_moves = Move.browse()
        orig_moves_by_move = {}
        unlinked_qty_by_move = {}

        for move in self:
            quantity_todo = move.product_uom_qty
            # Retain incomplete moves of the original ids
            updated_origin_moves = Move.browse()
            # Include the subsequent completed moves from self
            for move_line in move.move_line_ids:
                previous_mls = origin_mls.filtered(self._make_mls_comparison_lambda(move_line))
                quantity_todo -= sum(previous_mls.mapped("qty_done"))

                updated_origin_moves |= previous_mls.move_id
            if quantity_todo > 0:
                unlinked_qty_by_move[move] = quantity_todo
            orig_moves_by_move[move] = updated_origin_moves
            used_origin_moves |= updated_origin_moves

        # Some moves were not linked, possibly because of not having move lines
        if unlinked_qty_by_move:
            free_origin_moves_by_prod_qty = {}
            for origin_move in origin_moves.filtered(lambda m: m not in used_origin_moves):
                # Assign each orig move to a key made up of:
                # - Product ID
                # - Product Qty
                prod_qty_key = (origin_move.product_id.id, origin_move.product_uom_qty)
                free_origin_moves_by_prod_qty[prod_qty_key] = origin_move

            if len(unlinked_qty_by_move) == 1:
                # Special case: total unused origin quantities match the unlinked quantity.
                move, prod_qty = list(unlinked_qty_by_move.items())[0]
                rounding = move.product_id.uom_id.rounding
                unused_origs = origin_moves.filtered(
                    lambda m: m.product_id == move.product_id and m not in used_origin_moves
                )
                unused_qty = math.fsum(unused_origs.mapped("product_uom_qty"))
                if float_compare(prod_qty, unused_qty, precision_rounding=rounding) == 0:

                    orig_moves_by_move[move] |= unused_origs
                    for unused_orig in unused_origs:
                        free_origin_moves_by_prod_qty.pop(
                            unused_orig.product_id.id, unused_orig.product_uom_qty
                        )
            else:

                for move, prod_qty in unlinked_qty_by_move.items():
                    try:
                        new_origin_move = free_origin_moves_by_prod_qty.pop(
                            (move.product_id.id, prod_qty)
                        )
                        orig_moves_by_move[move] |= new_origin_move
                    except KeyError:
                        _logger.warning(
                            _("Unable to find origin move for %sx%s"),
                            move.product_id.name,
                            prod_qty,
                        )

        for move, origin_moves in orig_moves_by_move.items():
            move.write({"move_orig_ids": [(6, 0, origin_moves.ids)]})

    def _action_done(self, cancel_backorder=False):
        """
        Extend _action_done to trigger merge quants and to delete empty quants action.

        After _action_done is finished calling the _quant_tasks method which is defined in base core
        module and is merging and after deleting empty quants
        """
        Quant = self.env["stock.quant"]
        result = super()._action_done(cancel_backorder=cancel_backorder)

        Quant._quant_tasks()
        return result

    def _action_assign(self):
        """
        Assign moves and return all moves to the caller.

        Technically this is a LSP violation, as Odoo core coes not return the
        moves. However we want to ensure that we capture all assigned moves in
        the event that some are added or removed, for example through
        refactoring.
        """
        super()._action_assign()
        return self
