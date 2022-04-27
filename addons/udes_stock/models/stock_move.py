from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError


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
        self.move_line_ids.write({"qty_done": 0})
        return super()._action_cancel()

    def _do_unreserve(self):
        """
        Extend _do_unreserve to remove extra quantities added to initial_demand when
        unreserving a package.
        """
        res = super()._do_unreserve()
        for move in self:
            move.write({"product_uom_qty": move.u_uom_initial_demand})
        return res

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
        """Override stock default function to keep the old move lines,
        so there is no need to create them again
        """
        self.ensure_one()
        self.move_line_ids.filtered(lambda ml: ml.qty_done == 0.0).write(
            {"move_id": new_move.id, "product_uom_qty": 0}
        )

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
            and not self.move_orig_ids.filtered(lambda m: m.state not in ("done", "cancel"))
            and not self.state == "partially_available"
        ):
            new_move = self
            new_move.write({"picking_id": None})
        else:
            new_move_qty = sum(move_lines.mapped("product_uom_qty"))
            remaing_move_qty = self.product_uom_qty - new_move_qty
            new_move = self._create_split_move(move_lines, remaing_move_qty, new_move_qty, **kwargs)

        return new_move

    def split_out_incomplete_move(self, **kwargs):
        """
        Split a partially complete move up into complete and incomplete moves.
        This is essentially the reverse of split_out_move_line.
        A new move is created for all incomplete work, and an old move is
        adjusted to have the quantity in the move that is done. The original
        move lines persist in the original move.

        :returns: The created move
            If a move with nothing is complete, return an empty record set
            If a move is where everything is incomplete return self
        :raises: An error if move lines attached to self are partially complete.
        """
        Move = self.env["stock.move"]
        self.ensure_one()

        mls = self.move_line_ids

        # Raise an error if any of the move lines are partially fulfilled
        if mls and any(ml.qty_done != 0 and ml.qty_done < ml.product_uom_qty for ml in mls):
            raise ValidationError(
                _("You cannot create a backorder for %s with a move line qty less than expected!")
                % self.picking_id.name
            )

        # Check if there is something to split
        if self.quantity_done == 0:
            # Clear the picking information
            self.write({"picking_id": False})
            if mls:
                mls.write({"picking_id": False})
            return self
        elif self.product_uom_qty == self.quantity_done:
            return Move.browse()

        # Split the move
        # Manually create a new one and move the remaining quantity into it,
        # along with previously created move lines with qty_done == 0.
        total_move_qty = self.product_uom_qty
        total_done_qty = sum(mls.mapped("qty_done"))
        new_move_qty = int(total_move_qty - total_done_qty)

        incomplete_move_lines = mls.filtered(lambda ml: ml.qty_done == 0)
        return self._create_split_move(
            incomplete_move_lines, total_done_qty, new_move_qty, **kwargs
        )

    def _create_split_move(self, move_lines, remaining_qty, new_move_qty, **kwargs):
        """
        Logic to split a move into two.

        :args:
            move_lines: the move lines to be placed into the new move
            new_move_qty: the new move quantity (not equal to move line
            quantity since partially avialble moves could occur.)
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
        incomplete_moves = (self | new_move).filtered(lambda mv: mv.state not in ["done", "cancel"])
        incomplete_moves._recompute_state()

        move_lines.write({"state": new_move.state})

        # TODO
        # if self.move_orig_ids:
        #     (new_move | self).update_orig_ids(self.move_orig_ids)

        return new_move
