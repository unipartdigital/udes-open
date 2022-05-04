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
