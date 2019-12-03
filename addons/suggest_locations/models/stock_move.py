from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        values = super()._prepare_move_line_vals(quantity, reserved_quant)

        MoveLine = self.env["stock.move.line"]

        location = MoveLine.suggest_locations(
            limit=1,
            picking_type=self.picking_id.picking_type_id,
            values=values,
            preprocessing=True,
        )

        if location:
            values["location_dest_id"] = location.id

        return values
