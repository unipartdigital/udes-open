from odoo import fields, models, api, _
from odoo.exceptions import UserError
from itertools import groupby


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    u_grouping_key = fields.Char("Key", compute="_compute_grouping_key")

    def _compute_grouping_key(self):
        """Compute grouping key from move line"""
        StockPickingType = self.env["stock.picking.type"]

        # The environment must include {'compute_key': True}
        # to allow the keys to be computed.
        compute_key = self.env.context.get("compute_key")

        for move_line in self:
            grouping_key = None
            if compute_key:
                format_str = move_line.picking_id.picking_type_id.u_move_line_key_format
                if format_str:
                    # Generating a list of fields that are in u_move_line_key_format.
                    move_line_fields = StockPickingType.get_fields_from_key_format(format_str)
                    move_line_vals = {
                        field_name: move_line[field_name] for field_name in move_line_fields
                    }
                    grouping_key = format_str.format(**move_line_vals)

            move_line.u_grouping_key = grouping_key

    def group_by_key(self):
        """Check each picking type has a move line key format set and return the groupby"""
        if any(
            picking_type.u_move_line_key_format is False
            for picking_type in self.picking_id.picking_type_id
        ):
            raise UserError(
                _("Cannot group move lines when their picking type has no grouping key set.")
            )

        by_key = lambda ml: ml.u_grouping_key
        return {
            key: self.browse([move_line.id for move_line in group])
            for key, group in groupby(
                sorted(self.with_context(compute_key=True), key=by_key), key=by_key
            )
        }
