from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockLocationUnreserve(models.TransientModel):
    _name = "stock.location.unreserve"
    _description = "Unreserve Stock Wizard"

    affected_move_line_ids = fields.Many2many(
        "stock.move.line",
        string="Affected Move Lines",
        relation="stock_move_line_stock_location_unreserve_rel",
        readonly=True,
    )

    affected_picking_ids = fields.Many2many(
        "stock.picking",
        string="Affected Pickings",
        relation="stock_picking_stock_location_unreserve_rel",
        readonly=True,
    )

    affected_move_ids = fields.Many2many(
        "stock.move",
        string="Affected Moves",
        relation="stock_move_stock_location_unreserve_rel",
        readonly=True,
    )
    location_id = fields.Many2one("stock.location", "Location")

    @api.model
    def default_get(self, fields):
        """Override default get to set values of affected pickings, moves and move lines.

        Args:
            fields (list): list of fields

        Returns:
            dict: Returns fields dictionary with values
        """
        StockMoveLine = self.env["stock.move.line"]
        res = super().default_get(fields)

        location_id = self._context.get("active_id", False)
        res.update({"location_id": location_id})
        affected_move_lines = StockMoveLine.search(
            [
                ("state", "not in", ("cancel", "done")),
                ("location_id", "=", location_id),
                ("qty_done", "=", 0),
            ]
        )

        affected_moves = affected_move_lines.move_id
        affected_pickings = affected_move_lines.picking_id
        res.update(
            {
                "affected_move_line_ids": [(6, 0, affected_move_lines.ids)],
                "affected_move_ids": [(6, 0, affected_moves.ids)],
                "affected_picking_ids": [(6, 0, affected_pickings.ids)],
            }
        )
        return res

    def action_unreserve(self):
        """Unreserve affected moves which will delete all unpicked items reserved on current location."""
        self.ensure_one()
        self.affected_move_ids.with_context(
            bypass_constrain_blocked=True, skip_picked_qty=True
        )._do_unreserve()
        return {"type": "ir.actions.act_window_close"}
