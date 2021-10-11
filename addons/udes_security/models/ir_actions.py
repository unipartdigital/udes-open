from collections import defaultdict

from odoo import api, models


class IrActions(models.Model):
    _inherit = "ir.actions.actions"

    @api.model
    def get_bindings(self, model_name):
        """Override to not add any actions if the user is set to view only on desktop"""
        if self.env.user.u_desktop_readonly:
            return defaultdict(list)
        else:
            return super().get_bindings(model_name=model_name)
