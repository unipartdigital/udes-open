from odoo import models


class ResGroups(models.Model):
    _inherit = "res.groups"

    def write(self, vals):
        """Extend write:
        If we change the name of a group directly linked to a User Template,
        try to propagate the name change to the User Template
        """
        UserTemplate = self.env["user.template"]

        if (
            "name" in vals
            and vals.get("name")
            and not self.env.context.get("bypass_name_propagation_to_template")
        ):
            # @Performance: Ideally we would have a link back directly, but because
            # the relationship is effectively one2one, we would require a funky hack like this one:
            # http://blog.odoobiz.com/2014/10/openerp-one2one-relational-field-example.html
            template_for_group = UserTemplate.search([("template_group_id", "=", self.id)])
            if template_for_group:
                # NB: There can only be one due to constraints in place
                template_for_group._set_user_template_name(vals.get("name"))
        return super().write(vals)
