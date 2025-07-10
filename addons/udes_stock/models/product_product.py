from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from . common import check_upper_case_validation
import logging

_logger = logging.getLogger(__name__)


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
                msg = _(("%s numbers %s already in use for product %s")
                    % (self.tracking.capitalize(), " ".join(lots.mapped("name")), self.name))
                _logger.info(msg)
                # Only raise to avoid duplicate serials, but allow the same lot
                if self.tracking == "serial":
                    raise ValidationError(msg)

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

        return bool(stock_pickings) or self.get_quant_counts()

    def convert_measure_type_quantity(self, quantity, measure_type, reverse=False):
        """
        Getting the quantity in eaches when user selects a measure type, and the quantity is for measure selected.
        """
        self.ensure_one()
        measure_qty = 0
        quantity_factor = 1
        # Multiplying product quantity with number of products per pack/carton/pallet depending on what user
        # have selected.
        if measure_type:
            quantity_factor = measure_type == "none" and 1 or getattr(self, measure_type, None)
            if reverse:
                measure_qty = int(quantity/quantity_factor)
            elif measure_type and reverse:
                measure_qty = quantity
                quantity *= quantity_factor
        return quantity, measure_qty, quantity_factor

    def find_next_picking_product_measure_type(self, picked_quantity):
        """
        Getting the expected measure type quantity from quantity
        """
        self.ensure_one()
        carton_quantity_factor = self.u_carton_qty
        picked_quantity = int(picked_quantity)
        # Returning number of cartons if there are full number of cartons, picking with eaches otherwise.
        quantity = picked_quantity // carton_quantity_factor
        measure_type = "u_carton_qty"
        measure_type_label = "Cartons"
        if not quantity:
            quantity = picked_quantity % carton_quantity_factor
            measure_type = "none"
            measure_type_label = "Eaches"
        return str(quantity), measure_type, measure_type_label

    @api.model
    def create(self, vals):
        check_upper_case_validation(self._name, self.env.user, vals)
        return super().create(vals)

    def write(self, vals):
        check_upper_case_validation(self._name, self.env.user, vals)
        return super().write(vals)

    def get_barcode(self):
        """
        Get barcode of the product depending on configuration
        """
        self.ensure_one()
        if self.u_multiple_barcodes:
            barcode = self.u_barcode_ids and self.u_barcode_ids[0].name or None
        else:
            barcode = self.barcode
        return barcode

    def get_all_barcodes(self):
        """
        Get all barcodes of a product.
        """
        self.ensure_one()
        if self.u_multiple_barcodes:
            list_barcodes = self.u_barcode_ids.mapped("name")
        else:
            # Always returning a list, even when only one barcode is in it.
            list_barcodes = [self.barcode]
        return list_barcodes

    @api.model
    def get_by_barcode(self, barcode):
        """
        Getting the product from barcode, looking in product table or product barcode table depending on the config.

        If barcode is a list of barcodes, of the same product. There are scenarios where is called like that.
        """
        Product = self.env["product.product"]
        ProductBarcode = self.env["product.barcode"]
        warehouse = self.env.ref("stock.warehouse0")
        product = Product.browse()
        if warehouse.u_product_multiple_barcodes:
            # Using in operator when searching for the product, as the first one might be a new barcode.
            # We want to make sure product doesn't exist.
            if not isinstance(barcode, list):
                barcode = [barcode]
            product_barcodes = ProductBarcode.search([("name", "in", barcode)], order="id")
            if product_barcodes:
                product = product_barcodes.product_tmpl_id.product_variant_ids
                if len(product) > 1:
                    raise ValidationError(
                        _("Can not determine a single product from the provided barcodes. Found: %s") % product.mapped(
                            "name"))
        else:
            # Because of sql_constraint there is only one record in case found
            product = Product.search([("barcode", "=", barcode)], order="id", limit=1)
        return product

    def _get_info(self, level, info_fields, extra_fields):
        """Inherit with super to extend _get_info by adding more values or tweaking existing ones."""
        result = super()._get_info(level=level, info_fields=info_fields, extra_fields=extra_fields)
        if "barcode" in result:
            product_barcodes = self.get_all_barcodes()
            result.update({
                "barcode": product_barcodes
            })
        return result
