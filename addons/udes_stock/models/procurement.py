from odoo import  models


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
