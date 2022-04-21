"""
Stock Quant model.

Quants store information about the quantities and locations of products in the
warehouse.
"""
from odoo import models


class StockQuant(models.Model):
    """Stock Quant model."""

    _inherit = "stock.quant"

    # These fields will be extracted by get_info().
    _get_info_field_names = {
        "available_quantity",
        "location_id",
        "package_id",
        "product_id",
        "quantity",
        "reserved_quantity",
    }
