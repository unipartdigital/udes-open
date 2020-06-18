# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request


class PutawayStrategy(http.Controller):
    def _process_suggested_inputs(self, move_line_ids):
        """Process request into a dict"""
        StockMoveLine = request.env["stock.move.line"]
        move_lines = StockMoveLine.browse(list(map(int, move_line_ids))).exists()
        if not move_lines:
            raise ValueError(_("No move lines found with id(s): {}").format(move_line_ids))
        return move_lines

    @http.route("/api/suggest-locations", type="json", auth="user")
    def suggest_locations(self, move_line_ids, limit=30):
        """Suggest drop off locations for move lines provided based on the
        policy set on the picking type.
        Args:
            move_line_ids (list[int]): The move lines for which you want the
                                       suggested locaton.
        Returns:
            list[locations]: The locations suggested.
        """
        move_lines = self._process_suggested_inputs(move_line_ids)
        return move_lines.suggest_locations(limit).get_info()
