from odoo import fields, models, _, api
from odoo.exceptions import ValidationError, UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    NON_NEGATIVE_FIELDS = [
        "weight",
        "volume",
        "list_price",
        "standard_price",
        "u_height",
        "u_length",
        "u_width",
        "sale_delay",
    ]

    def _get_default_multiple_barcode_configuration(self):
        """
        Default configuration when creating a new product, so the visibility of the fields will be depending on
        configuration value when we create new product.
        """
        warehouse = self.env.user.get_user_warehouse()
        return warehouse.u_product_multiple_barcodes

    @api.constrains(*NON_NEGATIVE_FIELDS)
    def _constrain_non_negative_values(self):
        for record in self:
            for field in record.NON_NEGATIVE_FIELDS:
                if getattr(record, field) < 0:
                    raise UserError(
                        _("Negative values for %s on %s are not allowed")
                        % (field, record.name)
                    )

    u_pack_qty = fields.Integer(
        "Quantity Per Pack",
        default=1,
        help=_("Quantity of products per pack.")
    )
    u_carton_qty = fields.Integer(
        "Quantity Per Carton",
        default=1,
        help=_("Quantity of products per Carton.")
    )
    u_pallet_qty = fields.Integer(
        "Quantity Per Pallet",
        default=1,
        help=_("Quantity of products per pallet.")
    )
    u_multiple_barcodes = fields.Boolean(
        string="Multiple Barcodes",
        compute="_compute_multiple_barcodes_config",
        default=_get_default_multiple_barcode_configuration,
        help="Computed field, added in order to show the product barcodes field in product form view "
             "lines when config on the warehouse is enabled.",
    )
    u_barcode_ids = fields.One2many(
        "product.barcode", string="Product Barcodes", compute="_compute_barcode_ids", inverse="_set_barcode_ids",
    )

    POSITIVE_FIELDS = [
        "u_pack_qty",
        "u_carton_qty",
        "u_pallet_qty",
    ]
    @api.constrains(*POSITIVE_FIELDS)
    def _constrain_positive_values(self):
        for record in self:
            for field in record.POSITIVE_FIELDS:
                if getattr(record, field) < 1:
                    raise UserError(
                        _("Only positive values for %s on %s are allowed")
                        % (field, record.name)
                    )

    @api.constrains("tracking", "active")
    def _constrain_tracking_in_allowed_tracking_values(self):
        for product_template in self:
            warehouse = self.env.ref("stock.warehouse0")
            # Allowed tracking types are saved in a single char field, comma separated.
            allowed_tracking_types_list = warehouse.u_allowed_tracking_types.split(",")
            tracking_types_mapping = {
                "none": "No Tracking",
                "lot": "Lots",
                "serial": "Serial Number"
            }
            # Clearing allowed tracking types which are not possible option of tracking types.
            allowed_tracking_types = [
                tracking for tracking in allowed_tracking_types_list if tracking in tracking_types_mapping.keys()
            ]
            if product_template.tracking not in allowed_tracking_types:
                    raise UserError(
                        _("You aren't allowed to track a product by %s.")
                        % tracking_types_mapping[product_template.tracking]
                    )

    def _compute_multiple_barcodes_config(self):
        """Computed field to show the configuration set on the warehouse for multiple barcodes."""
        warehouse = self.env.user.get_user_warehouse()
        for product in self:
            product.u_multiple_barcodes = warehouse.u_product_multiple_barcodes

    @api.depends("product_variant_ids", "product_variant_ids.u_barcode_ids")
    def _compute_barcode_ids(self):
        for p in self:
            if len(p.product_variant_ids) == 1:
                p.u_barcode_ids = p.product_variant_ids.u_barcode_ids
            else:
                p.u_barcode_ids = False

    def _set_barcode_ids(self):
        for p in self:
            if len(p.product_variant_ids) == 1:
                p.product_variant_ids.u_barcode_ids = p.u_barcode_ids

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
    # Adding a new field to calculate product volume, there is an existing field for product template in the core
    # modules, avoided to use that field as that is on both models product.template and product.product and is 0 if
    # there are product variants otherwise is volume of the unique product variant. The fields we depend on computing
    # the volume are on product.template, thought to use a new one and to let the core field without changing.
    u_volume = fields.Float(
        "Volume (m3)", compute="_compute_udes_volume", digits=(16, 6), store=True
    )

    @api.depends("u_height", "u_length", "u_width")
    def _compute_udes_volume(self):
        for template in self:
            template.u_volume = template.u_height * template.u_length * template.u_width

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

    @api.depends("product_variant_ids", "product_variant_ids.default_code")
    def _compute_default_code(self):
        """
        Override _compute_default_code to include inactive variants in its computation.

        Instead of using super(ProductTemplate, self.with_context(dict(active_test=False)))
        we have to use a hard domain search to include inactive variants,
        else odd caching issues happen _after_ this compute bubbles up to `compute_value()`
        in fields.py which leads to the field being set to False when being archived via EDI.
        """
        Product = self.env["product.product"]
        inactive_variants = Product.search(
            [
                ("active", "=", False),
                ("product_tmpl_id", "in", self.ids),
            ]
        )
        # Include inactive variants in this filter
        unique_variants = self.filtered(
            lambda template: len(
                template.product_variant_ids
                | inactive_variants.filtered(
                    lambda inactive_variant: inactive_variant.product_tmpl_id == template
                )
            )
            == 1
        )
        for template in unique_variants:
            # Include inactive variants in this filter
            variant = template.product_variant_ids | inactive_variants.filtered(
                lambda inactive_variant: inactive_variant.product_tmpl_id == template
            )
            template.default_code = variant.default_code

        for template in self - unique_variants:
            template.default_code = ""
