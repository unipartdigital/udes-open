"""
Stock picking model.

A picking is a collection of moves to be executed.
"""
from odoo import models


class StockPicking(models.Model):
    """Stock Picking model."""

    _inherit = "stock.picking"

    # These fields will be extracted by get_info().
    _get_info_field_names = {
        "location_dest_id",
        "move_line_ids",
        "origin",
        "picking_type_id",
        "priority",
        "state",
    }
