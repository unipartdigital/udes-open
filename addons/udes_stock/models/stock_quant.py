# -*- coding: utf-8 -*-

from odoo import models, _, api
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_round

from collections import defaultdict


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _get_removal_strategy_order(self, removal_strategy=None):
        """Change fifo removal strategy"""
        # NOTE: Preserve `NULLS FIRST` for `in_date` and use for `package_id` as well
        if removal_strategy == "fifo":
            return "in_date ASC NULLS FIRST, package_id ASC NULLS FIRST"
        return super()._get_removal_strategy_order(removal_strategy)

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

    def assert_entire_packages(self):
        """Ensure the recordset self contains all the quants in package present
        in the recordset."""
        packages = self.mapped("package_id")
        package_quant_ids = packages._get_contained_quants()

        diff = package_quant_ids - self
        if diff:
            prob_packs = diff.mapped("package_id")
            raise ValidationError(
                _("Not all quants have been taken.\n" "Incomplete Packages:\n" "%s")
                % (" ".join(prob_packs.mapped("name")))
            )

    def assert_valid_location(self, location_id):
        """Ensure the recorset self contains quants child of location_id"""
        # TODO: check this function again, create generic is_valid/are_valid?
        Location = self.env["stock.location"]
        n_quant_locs = len(self.mapped("location_id"))
        child_locs = Location.search(
            [("id", "child_of", location_id), ("id", "in", self.mapped("location_id.id"))]
        )
        if len(child_locs) != n_quant_locs:
            raise ValidationError(
                _("The locations of some quants are not children of" " location %s")
                % Location.browse(location_id).name
            )

    def _gather(self, product_id, location_id, **kwargs):
        """Call default _gather function, if quant_ids context variable
        is set the resulting quants are filtered by id.

        Context variable quant_ids might contain quants of different products.
        """
        quants = super(StockQuant, self)._gather(product_id, location_id, **kwargs)
        quant_ids = self.env.context.get("quant_ids")
        if quant_ids:
            quants = quants.filtered(lambda q: q.id in quant_ids)
        return quants

    def total_quantity(self):
        """Returns the total quantity of the quants in self"""
        return sum(self.mapped("quantity"))

    def group_quantity_by_product(self, only_available=False):
        """Returns a dictionary with the total quantity per product,
        mapped by product_id.
        """
        products = defaultdict(int)
        for quant in self:
            product_id = quant.product_id.id
            value = quant.quantity
            if only_available:
                value -= quant.reserved_quantity
            # Only update if needed
            if value != 0:
                products[product_id] += value
        # Remove any empty product from the dict
        products = dict([(k, v) for k, v in products.items() if v != 0])
        return products

    def _prepare_info(self):
        """
        Prepares the following info of the quant in self:
        - id: int
        - package_id: {stock.quant.package}
        - parent_package_id: {stock.quant.package}
        - product_id: {product.product}
        - quantity: float
        - reserved_quantity: float
        - lot_id (optional): {stock.production.lot}
        """
        self.ensure_one()

        location_info = self.location_id.get_info()
        package_info = False
        parent_package_info = False
        if self.package_id:
            package_info = self.package_id.get_info()[0]
            if self.package_id.package_id:
                parent_package_info = self.package_id.package_id.get_info()[0]

        res = {
            "id": self.id,
            "package_id": package_info,
            "parent_package_id": parent_package_info,
            "product_id": self.product_id.get_info()[0],
            "location_id": location_info[0],
            "quantity": self.quantity,
            "reserved_quantity": self.reserved_quantity,
            "available_quantity": self.quantity - self.reserved_quantity,
        }

        if self.lot_id:
            res["lot_id"] = self.lot_id.get_info()[0]

        return res

    def get_info(self):
        """Return a list with the information of each quant in self."""
        res = []
        for quant in self:
            res.append(quant._prepare_info())

        return res

    @api.one
    @api.constrains("location_id")
    def quant_location_policy(self):
        self.location_id.apply_quant_policy()

    def get_move_lines(self, aux_domain=None):
        """Get the move lines associated with a quant
        :param aux_domain: Extra domain arguments to add to the search
        :returns: Associated move lines
        """
        self.ensure_one()
        MoveLine = self.env["stock.move.line"]
        domain = [
            ("product_id", "=", self.product_id.id),
            ("package_id", "=", self.package_id.id),
            ("location_id", "=", self.location_id.id),
            ("lot_id", "=", self.lot_id.id),
            ("owner_id", "=", self.owner_id.id),
        ]
        if aux_domain is not None:
            domain.extend(aux_domain)
        return MoveLine.search(domain)

    @api.multi
    def _split(self, qty):
        """Split a quant into two quants, a new quant with quantity `qty` and the original quantity
        of self reduced by qty. If qty > quantity, it just returns self (original quant).
        It gives the new quantity priority over reserved quantities.

        :param qty: Quantity to split from self, creating a new quant of quantity `qty`
        :return: new quant or self if it cannot be split

        Note: The quants are split and are the same but for the quantity and reserved quantity.
        This means when using get_quants() on a picking's the move lines it searches
        by location, product, lot, owner and package so the quants `new_quant` and `self` are
        exactly the same in get_quants() opinion. In this case using get_quants() on a picking's
        mls returns a candidate list of quants that match this criteria, and either an extra filter
        needs to be used or when completing a picking it should first order the quants by the
        amount reserved.
        """
        self.ensure_one()
        rounding = self.product_id.uom_id.rounding
        if (
            float_compare(abs(self.quantity), abs(qty), precision_rounding=rounding) <= 0
        ):  # if quant <= qty in abs, take it entirely
            return self
        # Update the quantities
        new_qty_round = float_round(qty, precision_rounding=rounding)
        qty_round = float_round(self.quantity - qty, precision_rounding=rounding)
        # Handle reserved quants
        reserved_quantity = self.reserved_quantity
        old_qty_round_reserved = float_round(
            self.reserved_quantity - qty, precision_rounding=rounding
        )
        new_quant = self.sudo().copy(
            default={
                "quantity": new_qty_round,
                "reserved_quantity": new_qty_round
                if old_qty_round_reserved > 0
                else reserved_quantity,
            }
        )
        self.sudo().write(
            {
                "quantity": qty_round,
                "reserved_quantity": old_qty_round_reserved if old_qty_round_reserved > 0 else 0,
            }
        )
        return new_quant

    @api.model
    def get_available_quantity(self, product, locations):
        """Get available quantity of product_id within locations."""
        domain = [("product_id", "=", product.id), ("location_id", "child_of", locations.ids)]
        quants = self.search(domain)
        available_quantity = sum(quants.mapped("quantity")) - sum(
            quants.mapped("reserved_quantity")
        )
        return available_quantity
