from odoo import models, fields


class Inventory(models.Model):
    _inherit = "stock.inventory"
    _description = "Inventory Adjustment"

    # Make locations field mandatory
    location_ids = fields.Many2many(required=True)

    u_line_default_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Default Line Location",
        compute="_compute_line_contextual_fields",
        help="Technical field used for determining the default location set on lines",
    )
    u_line_readonly_location_id = fields.Boolean(
        string="Readonly Line Location",
        compute="_compute_line_contextual_fields",
        help="Technical field used for determining whether the location field on lines is readonly",
    )
    u_line_default_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Default Line Product",
        compute="_compute_line_contextual_fields",
        help="Technical field used for determining the default product set on lines",
    )
    u_line_readonly_product_id = fields.Boolean(
        string="Readonly Line Product",
        compute="_compute_line_contextual_fields",
        help="Technical field used for determining whether the product field on lines is readonly",
    )

    def _compute_line_contextual_fields(self):
        """
        Compute fields used solely for usability purposes in the UI. These fields are only
        properly calculated when the inventory adjustment is in progress.

        In vanilla Odoo the inventory adjustment details are handled in a dedicated tree view of
        inventory lines, with various settings applied on top of the core action when the user
        clicks to start or continue the adjustment.

        In UDES, inventory adjustments will be carried out within the main form view, so the user
        always has full visibility of the top level details of the inventory adjustment, as well
        as the traceability of what was counted. This means we are more limited with our options
        for locking down certain fields, as client side evaluations will not be enough.

        Partially mimics the behavior Odoo has for the adjustment details screen:
            * If adjustment is for one location, make this the default
            * If adjustment is for one location, and the location doesn't have children, make
              this field readonly
            * If adjustment is for one product, make this the default and readonly
        """
        Location = self.env["stock.location"]

        # We only care about inventory adjustments that are in progress
        inventory_recs_to_skip = self.filtered(lambda i: i.state != "confirm")
        for inventory in inventory_recs_to_skip:
            inventory.u_line_default_location_id = False
            inventory.u_line_readonly_location_id = False
            inventory.u_line_default_product_id = False
            inventory.u_line_readonly_product_id = False

        for inventory in self - inventory_recs_to_skip:
            default_location_id = False
            readonly_location_id = False
            default_product_id = False
            readonly_product_id = False

            inv_locations = inventory.location_ids.with_context(prefetch_fields=False)
            if len(inv_locations) == 1:
                default_location_id = inv_locations
                inv_location_has_children = bool(
                    Location.search_count([("location_id", "=", inv_locations.id)])
                )
                readonly_location_id = not inv_location_has_children

            inv_products = inventory.product_ids.with_context(prefetch_fields=False)
            if len(inv_products) == 1:
                default_product_id = inv_products
                readonly_product_id = True

            inventory.u_line_default_location_id = default_location_id
            inventory.u_line_readonly_location_id = readonly_location_id
            inventory.u_line_default_product_id = default_product_id
            inventory.u_line_readonly_product_id = readonly_product_id

    def action_start(self):
        """Override to prevent user being redirected to inventory line view"""
        super().action_start()
        return True

    def action_open_inventory_lines(self):
        """
        Override to remove functionality of the method,
        as we want to adjust inventory in the main form view
        """
        return
