"""UDES Stock Warehouse model and related code."""
from odoo import fields, models


class StockWarehouse(models.Model):
    """A warehouse instance contains high-level configuration for a warehouse."""

    _name = "stock.warehouse"
    _inherit = ["stock.warehouse"]

    # "UDES" is the default prefix for package names (it is defined in UDES Stock).
    u_pallet_barcode_regex = fields.Char("Pallet Barcode Format", default="^UDES(?:[0-9])+$")
    u_package_barcode_regex = fields.Char("Package Barcode Format", default="^[0-9]+$")
