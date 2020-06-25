# -*- coding: utf-8 -*-
from itertools import groupby

from odoo import fields, models
from odoo.exceptions import UserError


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    u_grouping_key = fields.Char("Key", compute="compute_grouping_key")

    def compute_grouping_key(self):
        """Compute grouping key from move line"""
        # The environment must include {'compute_key': True}
        # to allow the keys to be computed.
        if not self.env.context.get("compute_key", False):
            return
        for move_line in self:
            move_line_vals = {
                fname: getattr(move_line, fname)
                for fname in move_line._fields.keys()
                if fname != "u_grouping_key"
            }
            format_str = move_line.picking_id.picking_type_id.u_move_line_key_format

            if format_str:
                move_line.u_grouping_key = format_str.format(**move_line_vals)
            else:
                move_line.u_grouping_key = None

    def group_by_key(self):
        """Check each picking type has a move line key format set and return the groupby"""
        if any(pt.u_move_line_key_format is False for pt in self.picking_id.picking_type_id):
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
