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
        self.ensure_one()
        Orderpoint = self.env["stock.warehouse.orderpoint"]
        orderpoints = Orderpoint.search(
            [
                ("location_id", "=", self.location_id.id),
            ]
        )
        orderpoints -= self
        if not orderpoints:
            return
        if not self.location_id.limits_orderpoints():
            return
        names = ", ".join(orderpoints.mapped("product_id.name"))
        raise ValidationError(
            _("An order point for location {} already exists on " "{}.").format(
                self.location_id.name, names
            )
        )
