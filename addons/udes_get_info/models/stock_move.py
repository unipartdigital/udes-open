"""
Stock move model.

Moves describe an operation to move quantities of things from one location to
another.  Moves do not specify details such as packages, this is left to move
lines.
"""
from odoo import models


class StockMove(models.Model):
    """Stock Move model."""

    _inherit = "stock.move"

    # These fields will be extracted by get_info().
    _get_info_field_names = {
        "location_dest_id",
        "location_id",
        "move_line_ids",
        "product_id",
        "product_qty",
        "product_uom",
        "product_uom_qty",
        "quantity_done",
        "state",
    }
