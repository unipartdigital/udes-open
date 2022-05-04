from odoo import api, models, _, registry


class ProcurementGroup(models.Model):
    _name = "procurement.group"
    # Add mixin stock model
    _inherit = ["procurement.group", "mixin.stock.model"]

    # Allow groups to be created
    MSM_CREATE = True

    def _get_orderpoint_domain(self, company_id=False):
        """ Override order point domain to filter by active_ids
        """
        domain = super()._get_orderpoint_domain(company_id=company_id)
        orderpoints = self.env.context.get('active_ids', None)
        if orderpoints:
            domain += [('id', 'in', orderpoints)]
        return domain

        
class StockWarehouseOrderPoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    @api.model
    def check_order_points(self, use_new_cursor=False, company_id=False):
        """
        Copy of run_scheduler from Odoo's stock module ProcurementGroup class.
        This allows us to only check order points.
        """
        OrderPoint = self.env["stock.warehouse.orderpoint"]
        ProcurementGroup = self.env["procurement.group"]
        try:
            if use_new_cursor:
                domain = ProcurementGroup._get_orderpoint_domain()
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

