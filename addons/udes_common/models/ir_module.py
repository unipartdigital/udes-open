from odoo import models, api


class Module(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def is_module_installed(self, module_name):
        """
        Returns true if the supplied module exists
        and is installed, otherwise false.
        """
        search_domain = [("name", "=", module_name), ("state", "=", "installed")]
        installed_module_count = self.search(search_domain, limit=1, order="id", count=True)
        module_installed = bool(installed_module_count)
        return module_installed
