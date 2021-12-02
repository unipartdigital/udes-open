# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        """Extend default function to use our own suggested location strategy"""
        MoveLine = self.env["stock.move.line"]
        values = super()._prepare_move_line_vals(quantity, reserved_quant)
        try:
            location = MoveLine.suggest_locations(limit=1, picking=self.picking_id, values=values,)
        except ValueError:
            _logger.warning("No suggest locations policy has been set!")
        else:
            if location:
                values["location_dest_id"] = location.id

        return values
