from odoo import fields, models, _


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "mixin.stock.model"]

    # Allow to search via both name and barcode
    MSM_STR_DOMAIN = ("name", "barcode")

    # Add tracking for archiving.
    active = fields.Boolean(tracking=True)

    def sync_active_to_templates(self, activate_templates=True, deactivate_templates=True):
        """ Copy the active state from products to their templates

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
            templates_to_deactivate = templates.filtered(lambda t: not t.product_variant_ids)
            templates_to_deactivate.write({"active": False})

        if activate_templates:
            templates_to_activate = templates.filtered(lambda t: t.product_variant_ids)
            templates_to_activate.write({"active": True})
