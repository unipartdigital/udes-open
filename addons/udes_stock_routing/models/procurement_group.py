from odoo import models, api
from odoo.osv import expression


class ProcurementGroup(models.Model):
    _inherit = "procurement.group"

    @api.model
    def _get_rule_domain(self, location, values):
        """Extend rule domain search to exclude rules which run on stock assignment"""
        res = super()._get_rule_domain(location, values)
        res = expression.AND([res, [("u_run_on_assign", "=", False)]])
        return res
