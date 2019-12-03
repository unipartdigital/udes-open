# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request


class PutawayStrategy(http.Controller):
    def _process_suggested_inputs(self, move_line_ids, limit=30, **kwargs):
        """Process request into a dict"""
        move_lines = request.env["stock.move.line"].browse(move_line_ids)
        values = {"limit": limit}
        if not move_lines:
            raise ValueError(
                _("No move lines found with id(s): {}").format(move_line_ids)
            )
        return move_lines, values

    @http.route("/api/suggest-location", type="json", auth="user")
    def suggest_location(self):
        """Suggest drop off locations for move lines provided based on the
        policy set on the picking type.

        Args:
            move_line_ids (list[int]): The move lines for which you want the
                                       suggested locaton.

        Returns:
            list[locations]: The locations suggested.
        """
        move_lines, values = self._process_suggested_inputs(**request.jsonrequest)
        return move_lines.suggest_locations(**values).get_info()
