from odoo import fields, models, _, api
from odoo.exceptions import ValidationError


class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    @api.onchange("location_id")
    @api.constrains("location_id")
    def _is_limited(self):
        """Prevents creating a second order point on a location.

        If the location or an ancestor is configured to only allow a single
        order point.

        Raises a ValidationError if the constraint is breached.
        """
        Orderpoint = self.env["stock.warehouse.orderpoint"]

        for orderpoint in self:
            orderpoints = Orderpoint.search(
                [
                    ("location_id", "=", orderpoint.location_id.id),
                ]
            )
            orderpoints -= orderpoint
            if orderpoints and orderpoint.location_id.limits_orderpoints():
                names = ", ".join(orderpoints.mapped("product_id.name"))
                raise ValidationError(
                    _("An order point for location {} already exists on " "{}.").format(
                        orderpoint.location_id.name, names
                    )
                )

    @api.model
    def create(self, vals):
        """
        Override create to include product's _compute_nbr_reordering_rules()
        to check whether we need to add "replen" route.
        """
        res = super().create(vals)
        res.product_id._compute_nbr_reordering_rules()
        return res

    def write(self, vals):
        """
        Override write to include product's _compute_nbr_reordering_rules()
        There might be a chance where a user changes product on "stock.warehouse.orderpoint" record
        in this case we need to check on new product as well as on old product weather we need to
        add/remove "replen" route.
        """
        products_to_update = self.mapped("product_id")
        res = super().write(vals)
        products_to_update |= self.product_id
        products_to_update._compute_nbr_reordering_rules()
        return res

    def unlink(self):
        """
        Override unlink to include product's _compute_nbr_reordering_rules()
        Map products before unlink is performed then browse products to check
        weather we need to remove "replen" route.
        """
        products_to_update = self.mapped("product_id")
        res = super().unlink()
        Product = self.env["product.product"].browse(products_to_update.ids)
        Product._compute_nbr_reordering_rules()
        return res

