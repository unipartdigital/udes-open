from odoo import fields, models, _, api, registry
from odoo.osv import expression
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
    def check_order_points(self, use_new_cursor=False, company_id=False, location_id=False, excluded_location_ids=False):
        """
        Copy of run_scheduler from Odoo's stock module ProcurementGroup class.
        This allows us to only check order points.
        """
        OrderPoint = self.env["stock.warehouse.orderpoint"]
        ProcurementGroup = self.env["procurement.group"]
        try:
            if use_new_cursor:
                domain = ProcurementGroup._get_orderpoint_domain()
                if location_id:
                    domain = expression.AND([domain, [("location_id", "=", location_id)]])
                if excluded_location_ids:
                    domain = expression.AND([domain, [("location_id", "not in", excluded_location_ids)]])
                self = OrderPoint.with_context(prefetch_fields=False).search(domain)
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))

            self.sudo()._procure_orderpoint_confirm(
                use_new_cursor=use_new_cursor,
                company_id=company_id)
            if use_new_cursor:
                self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}
