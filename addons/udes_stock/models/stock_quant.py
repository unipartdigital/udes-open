from odoo import models, _, api
from collections import defaultdict
from odoo.exceptions import ValidationError


class StockQuant(models.Model):
    _inherit = "stock.quant"
    _description = "Quant"

    @api.model
    def _get_removal_strategy_order(self, removal_strategy=None):
        """Change fifo removal strategy"""
        # NOTE: Preserve `NULLS FIRST` for `in_date` and use for `package_id` as well
        if removal_strategy == "fifo":
            return "in_date ASC NULLS FIRST, package_id ASC NULLS FIRST"
        return super(StockQuant, self)._get_removal_strategy_order(removal_strategy)

    def assert_not_reserved(self):
        """Ensure all quants in the recordset are unreserved."""
        reserved = self.filtered(lambda q: q.reserved_quantity > 0)
        if reserved:
            raise ValidationError(
                _(
                    "Items are reserved and cannot be moved. "
                    "Please speak to a team leader to resolve "
                    "the issue.\nAffected Items: %s"
                )
                % (
                    " ".join(reserved.mapped("package_id.name"))
                    if reserved.mapped("package_id")
                    else " ".join(reserved.mapped("product_id.display_name"))
                )
            )

    def _gather(self, product_id, location_id, **kwargs):
        """Call default _gather function, if quant_ids context variable
        is set the resulting quants are filtered by id.
        This allows to reserve specific quants instead of following the default
        policy.
        Context variable quant_ids might contain quants of different products.
        """
        quants = super(StockQuant, self)._gather(product_id, location_id, **kwargs)
        quant_ids = self.env.context.get("quant_ids")
        if quant_ids:
            quants = quants.filtered(lambda q: q.id in quant_ids)
        return quants

    def get_quantity(self):
        """Returns the total quantity of the quants in self"""
        return sum(self.mapped("quantity"))

    def get_quantities_by_key(self, get_key=lambda q: q.product_id, only_available=False):
        """Returns a dictionary with the total quantity per product, mapped by product_id.
        :kwargs:
            - only_available: Boolean
                Whether to include those reserved or not in the grouping
            - get_key: a callable which takes a quant and returns the key
        :returns:
            a dictionary with the total quantity per product,
                mapped by get_key or product_id as default
        """
        products = defaultdict(int)
        for quant in self:
            value = quant.quantity
            if only_available:
                value -= quant.reserved_quantity
            products[get_key(quant)] += value
        return products

    def to_products_info(self, only_available=False):
        product_quantities = self.get_quantities_by_key(only_available=only_available)
        products_info = [
            {"product": key, "uom_qty": val} for key, val in product_quantities.items()
        ]

        return products_info

    def create_picking(self, picking_type, only_available=False, **kwargs):
        """
        Create a picking from quants
        Uses stock.picking create_picking functionality to create the picking.
        Note that the quants are stored in the product uom.

        :args:
            - picking_type
        :kwargs:
            - Extra args for the create picking
        :returns:
            - picking
        """
        Picking = self.env["stock.picking"]

        if "location_id" not in kwargs:
            locations = self.location_id
            location = locations.get_common_ancestor()
            if location:
                kwargs.update({"location_id": location.id})

        products_info = self.to_products_info(only_available=only_available)

        return Picking.with_context(quant_ids=self.ids).create_picking(
            picking_type, products_info, **kwargs
        )

    @api.model
    def get_available_quantity(self, product, locations):
        """Get available quantity of product_id within locations."""
        Quant = self.env["stock.quant"]

        product.ensure_one()
        domain = self.get_available_qty_domain(product, locations)
        quants = self.search(domain).with_context(prefetch_fields=False)
        quants.read(["quantity", "reserved_quantity"], load="_classic_write")
        available_quantity = sum(quants.mapped("quantity")) - sum(
            quants.mapped("reserved_quantity")
        )
        return available_quantity

    def get_move_lines(self, aux_domain=None):
        """Get the move lines associated with a quant
        :param aux_domain: Extra domain arguments to add to the search
        :returns: Associated move lines
        """
        self.ensure_one()
        MoveLine = self.env["stock.move.line"]
        domain = self.get_move_lines_domain(aux_domain=aux_domain)
        return MoveLine.search(domain)

    def get_move_lines_domain(self, aux_domain=None):
        """
        Getting the domain in its own method, would be easier to reuse it when we need just domain
        and example to execute search_read or search method.
        It can be easier even if is needed to extend it with super without having to extend with
        aux_domain optional parameter
        """
        self.ensure_one()
        
        domain = [
            ("product_id", "=", self.product_id.id),
            ("package_id", "=", self.package_id.id),
            ("location_id", "=", self.location_id.id),
            ("lot_id", "=", self.lot_id.id),
            ("owner_id", "=", self.owner_id.id),
        ]
        if aux_domain is not None:
            domain.extend(aux_domain)
        return domain

    @api.model
    def get_available_qty_domain(self, product, locations):
        return [("product_id", "=", product.id), ("location_id", "child_of", locations.ids)]
