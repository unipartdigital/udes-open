from odoo import fields, models, _, api, registry
from odoo.osv import expression
from odoo.exceptions import ValidationError


class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    _sql_constraints = [
        (
            "product_min_qty_positive",
            "check (product_min_qty > 0)",
            _("Minimum Quantity must be greater than zero"),
        )
    ]

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
