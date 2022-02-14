# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _domain_product_category(self, category):
        """Domain for product categories, not including category itself"""
        return [("id", "child_of", category.id), ("id", "!=", category.id)]

    def _domain_height_category(self):
        """Domain for height product category"""
        category = self.env.ref("udes_stock.product_category_height")
        return self._domain_product_category(category)

    def _domain_speed_category(self):
        """Domain for speed product category"""
        category = self.env.ref("udes_stock.product_category_speed")
        return self._domain_product_category(category)

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility="onchange")

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)

    # Default to being a stockable product
    type = fields.Selection(default="product")

    u_hazardous = fields.Boolean(string="Hazardous", default=False)

    u_manufacturer_part_no = fields.Char(string="Mfr Part No", help="Manufacturer part number")

    u_height_category_id = fields.Many2one(
        comodel_name="product.category",
        domain=_domain_height_category,
        string="Product Category Height",
        help="Product category height to match with location height.",
    )
    u_speed_category_id = fields.Many2one(
        comodel_name="product.category",
        domain=_domain_speed_category,
        string="Product Category Speed",
        help="Product category speed to match with location speed.",
    )

    u_pallet_qty = fields.Float(
        string="Pallet Quantity",
        default=0.0,
        digits=dp.get_precision("Product Unit of Measure"),
        help="Quantity of product per pallet",
    )

    @api.onchange("u_pallet_qty")
    def disallow_negative_values(self):
        """Prevent values from going below 0."""
        if self.u_pallet_qty < 0:
            raise ValidationError("Value for pallet quantity cannot be below 0.")

    @api.onchange("tracking")
    def _confirm_lot_tracking_change(self):
        """Prevent accidental changes to lot tracking number."""
        if self.qty_available > 0:
            return {
                "warning": {
                    "title": _("Change Tracking Type"),
                    "message": _(
                        "Products already existing in locations will need to be stock checked."
                    ),
                }
            }

    @api.multi
    def unlink(self):
        """Override superclass to prevent deletion."""
        raise ValidationError(_("Products may not be deleted. Please archive them instead."))
