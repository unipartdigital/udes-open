# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp


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
            # NB: We have a single move, so a single product as it is a Many2one
            # so we do not need to worry about shuffling of uom's
            total_initial_qty = sum(move_lines.mapped("product_uom_qty"))
            default_values = {
                "picking_id": False,
                "move_line_ids": [],
                "move_orig_ids": [],
                # move_dest_ids not copied by default
                # WS-MPS: this might need to be refined like move_orig_ids
                "move_dest_ids": [(6, 0, self.move_dest_ids.ids)],
                "product_uom_qty": total_initial_qty,
                "state": self.state,
            }
            default_values.update(kwargs)
            new_move = self.copy(default_values)
            move_lines.write({"move_id": new_move.id, "picking_id": None})

            # Adding context variables to avoid any change to be propagated to
            # the following moves and do not unreserve any quant related to the
            # move being split.
            context_vars = {
                "bypass_reservation_update": True,
                "do_not_propagate": True,
                "do_not_unreserve": True,
            }
            self.with_context(**context_vars).write(
                {"product_uom_qty": self.product_uom_qty - total_initial_qty}
            )

            # When not complete, splitting a move may change its state,
            # so recompute
            incomplete_moves = (self | new_move).filtered(
                lambda mv: mv.state not in ["done", "cancel"]
            )
            incomplete_moves._recompute_state()

            move_lines.write({"state": new_move.state})

            if self.move_orig_ids:
                (new_move | self).update_orig_ids(self.move_orig_ids)

        return new_move
