"""
Stock move line model.

Move lines are actions required to complete a planned move, for example a move
of ten apples from A to B might require two lines: five apples from one
sublocation of A and five from another.
"""
from odoo import models


class StockMoveLine(models.Model):
    """Stock Move Line model."""

    _inherit = "stock.move.line"

    # These fields will be extracted by get_info().
    _get_info_field_names = {
        "create_date",
        "location_dest_id",
        "location_id",
        "lot_id",
        "package_id",
        "product_uom_qty",
        "qty_done",
        "result_package_id",
        "write_date",
    }
