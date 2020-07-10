# -*- coding: utf-8 -*-
from itertools import groupby

from odoo import fields, models, _
from odoo.exceptions import UserError


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    u_grouping_key = fields.Char("Key", compute="compute_grouping_key")

    def compute_grouping_key(self):
        """Compute grouping key from move line"""
        # The environment must include {'compute_key': True}
        # to allow the keys to be computed.

        # TODO: Look into making this computed field stored so it only needs 
        # to recalculate when the picking type move line key format is updated
        # and check for improvements to performance.
        if not self.env.context.get("compute_key", False):
            return
        for move_line in self:
            move_line_vals = {
                field_name: move_line[field_name]
                for field_name in move_line._fields.keys()
                if field_name != "u_grouping_key"
            }
            format_str = move_line.picking_id.picking_type_id.u_move_line_key_format

            if format_str:
                move_line.u_grouping_key = format_str.format(**move_line_vals)
            else:
                move_line.u_grouping_key = None

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
