from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "mixin.stock.model"]

    # Allow to search via both name and barcode
    MSM_STR_DOMAIN = ("name", "barcode")

    # Add tracking for archiving.
    active = fields.Boolean(tracking=True)

    def assert_tracking_unique(self, serial_numbers):
        """
        If the product in self is tracked, check if
        the ones in serial_numbers are currently in use in the system.
        """
        Lot = self.env["stock.production.lot"]
        self.ensure_one()
        if self.tracking != "none":
            lots = Lot.search(
                [("product_id", "=", self.id), ("name", "in", serial_numbers)]
            )
            if lots:
                raise ValidationError(
                    _("%s numbers %s already in use for product %s")
                    % (self.tracking.capitalize(), " ".join(lots.mapped("name")), self.name)
                )

    def sync_active_to_templates(
        self, activate_templates=True, deactivate_templates=True
    ):
        """Copy the active state from products to their templates

        Product templates will be active if any of their product variants are
        active, including product.products not present in self.
        """
        ProductTemplate = self.env["product.template"]

        self = self.with_context(prefetch_fields=False)
        templates = self.mapped("product_tmpl_id")

        # Prefetch fields
        templates.mapped("product_variant_ids")

        # Activate or deactivate templates based on product_variant_ids.
        # product_variant_ids only contains active products because Odoo
        # automatically adds active=True to its domain.

        if deactivate_templates:
            templates_to_deactivate = templates.filtered(
                lambda t: not t.product_variant_ids
            )
            templates_to_deactivate.write({"active": False})

        if activate_templates:
            templates_to_activate = templates.filtered(lambda t: t.product_variant_ids)
            templates_to_activate.write({"active": True})

    def unlink(self):
        """Override superclass to prevent deletion."""
        raise ValidationError(_("Products may not be deleted. Please archive them instead."))

    def get_quant_counts(self):
        warehouse = self.env.ref("stock.warehouse0")
        Quant = self.env["stock.quant"]
        quants = Quant.search_count(
            [
                ("product_id", "in", self.ids),
                ("location_id", "child_of", warehouse.view_location_id.id),
            ]
        )
        return quants

    def has_goods_in_transit_or_stock(self):
        Picking = self.env["stock.picking"]
        picking_type = self.env.ref("stock.picking_type_in")
        stock_pickings = Picking.search(
            [
                ("move_lines.product_id", "in", self.ids),
                ("state", "=", "assigned"),
                ("picking_type_id", "=", picking_type.id),
            ]
        )

        if self.get_quant_counts() > 0 or bool(stock_pickings):
            return True
        return False
