"""
Stock picking batch model.

A batch is a collection of pickings to be executed.
"""
from odoo import models


class StockPickingBatch(models.Model):
    """Stock Picking model."""

    _inherit = "stock.picking.batch"

    # These fields will be extracted by get_info().
    _get_info_field_names = {
        "state",
        "u_ephemeral",
        "picking_ids",
        "u_original_name",
    }
