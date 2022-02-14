# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from ..utils import BASE_PRODUCT_IMAGE_URL


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility="onchange")

    def assert_serial_numbers(self, serial_numbers):
        """
        If the product in self is tracked by serial numbers, check if
        the ones in serial_numbers are currently in use in the system.
        """
        Lot = self.env["stock.production.lot"]
        self.ensure_one()
        if self.tracking == "serial":
            lots = Lot.search([("product_id", "=", self.id), ("name", "in", serial_numbers)])
            if lots:
                raise ValidationError(
                    _("Serial numbers %s already in use for product %s")
                    % (" ".join(lots.mapped("name")), self.name)
                )

    def _prepare_info(self, fields_to_fetch=None):
        """
        Prepares the following info of the product in self:
        - id: int
        - barcode: string
        - display_name: string
        - name: string
        - tracking: string

        @param fields_to_fetch: array of string
            Subset of the default fields to return
        """
        self.ensure_one()

        def _prepare_image_urls(p):
            if p.image:
                base_url = BASE_PRODUCT_IMAGE_URL % p.id
                image_urls = {
                    "large": base_url + "/image",
                    "medium": base_url + "/image_medium",
                    "small": base_url + "/image_small",
                }
                return image_urls
            return {}

        info = {
            "id": lambda p: p.id,
            "barcode": lambda p: p.barcode,
            "display_name": lambda p: p.display_name,
            "name": lambda p: p.display_name,
            "tracking": lambda p: p.tracking,
            "image_urls": _prepare_image_urls,
        }

        if not fields_to_fetch:
            fields_to_fetch = info.keys()

        return {key: value(self) for key, value in info.items() if key in fields_to_fetch}

    def get_info(self, **kwargs):
        """Return a list with the information of each product in self."""
        res = []
        for prod in self:
            res.append(prod._prepare_info(**kwargs))

        return res

    def get_product(self, product_identifier):
        """Get product from a name, barcode, or id."""
        if isinstance(product_identifier, int):
            domain = [("id", "=", product_identifier)]
        elif isinstance(product_identifier, str):
            domain = ["|", ("barcode", "=", product_identifier), ("name", "=", product_identifier)]
        else:
            raise ValidationError(
                _("Unable to create domain for product search from identifier of type %s")
                % type(product_identifier)
            )

        results = self.search(domain)
        if not results:
            raise ValidationError(_("Invalid product scanned: %s") % str(product_identifier))
        if len(results) > 1:
            raise ValidationError(
                _("Too many products found for identifier %s") % str(product_identifier)
            )

        return results

    @api.multi
    def sync_active_to_templates(self, activate_templates=True, deactivate_templates=True):
        """Copy the active state from products to their templates

        Product templates will be active if any of their product variants are
        active, including product.products not present in self.
        """
        self = self.with_context(prefetch_fields=False)
        templates = self.mapped("product_tmpl_id")

        # Prefetch fields
        templates.mapped("product_variant_ids")

        # Activate or deactivate templates based on whether it has active product_variant_ids.

        if deactivate_templates:
            templates_to_deactivate = templates.filtered(
                lambda t: not t.product_variant_ids.filtered("active")
            )
            templates_to_deactivate.write({"active": False})

        if activate_templates:
            templates_to_activate = templates.filtered(
                lambda t: t.product_variant_ids.filtered("active")
            )
            templates_to_activate.write({"active": True})

    @api.multi
    def unlink(self):
        """Override superclass to prevent deletion."""
        raise ValidationError(_("Products may not be deleted. Please archive them instead."))
