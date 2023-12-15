from odoo import fields, models, _, api
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _domain_product_category(self, category):
        """Domain for product categories, not including category itself"""
        return [("id", "child_of", category.id), ("id", "!=", category.id)]

    def _domain_speed_category(self):
        """Domain for speed product category"""
        category = self.env.ref("udes_stock.product_category_speed")
        return self._domain_product_category(category)

    def _domain_height_category(self):
        """Domain for height product category"""
        category = self.env.ref("udes_stock.product_category_height")
        return self._domain_product_category(category)

    # Add tracking for archiving.
    active = fields.Boolean(tracking=True)

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)

    # Default to being a stockable product
    type = fields.Selection(default="product")

    u_speed_category_id = fields.Many2one(
        comodel_name="product.category",
        domain=_domain_speed_category,
        string="Product Category Speed",
        help="The speed in which the product can be processed.",
    )
    u_height_category_id = fields.Many2one(
        comodel_name="product.category",
        domain=_domain_height_category,
        index=True,
        string="Product Category Height",
        help="Product category height to match with location height.",
    )

    u_height = fields.Float(string="Height (m)", help="Product height in metres", default=0.0)
    u_length = fields.Float(string="Length (m)", help="Product length in metres", default=0.0)
    u_width = fields.Float(string="Width (m)", help="Product width in metres", default=0.0)

    def unlink(self):
        """Override superclass to prevent deletion."""
        raise ValidationError(_("Products may not be deleted. Please archive them instead."))
            
    @api.onchange("tracking")
    @api.constrains("tracking")
    def constrain_tracking(self):
        for product in self:
            if product.product_variant_ids.has_goods_in_transit_or_stock():
                # If there is stock, raise an error to prevent changing the tracking
                raise ValidationError(
                    _(
                        "Cannot change tracking for product '%s' with stock or move lines in ready state."
                    )
                    % product.name
                )
