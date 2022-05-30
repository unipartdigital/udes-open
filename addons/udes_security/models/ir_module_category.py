from odoo import models


class ModuleCategory(models.Model):
    _inherit = "ir.module.category"

    def set_groups_required_group_to_change_to_self(self):
        """For each category in self, set all linked groups' required group to change to itself"""
        Group = self.env["res.groups"]
        for category in self:
            groups = Group.search([("category_id", "=", category.id)], order="id")
            groups.set_required_group_to_change_to_self()
