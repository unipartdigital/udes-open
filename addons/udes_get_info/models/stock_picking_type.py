"""
Stock Picking Type model.

Picking types define the operations that can be performed in a warehouse.
"""
from odoo import models


class StockPickingType(models.Model):
    """Stock Picking Type model."""

    _inherit = "stock.picking.type"

    # These fields will be extracted by get_info().
    _get_info_field_names = {
        "code",
        "company_id",
        "count_picking_ready",
        "default_location_dest_id",
        "default_location_src_id",
        "display_name",
        "id",
        "name",
        "sequence",
        "warehouse_id",
    }
