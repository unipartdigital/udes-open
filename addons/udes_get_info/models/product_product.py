"""
Product model.

Products are based on product templates.
"""
from odoo import models


class ProductProduct(models.Model):
    """Product model."""

    _inherit = "product.product"

    # These fields will be extracted by get_info().
    _get_info_field_names = {
        "barcode",
        "tracking",
    }
