from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.multi
    def write(self, vals):
        password = self._context.get("password")
        if password:
            partner_user = self.user_ids and self.user_ids[0]

            partner_user._check_password(password)
        return super(ResPartner, self).write(vals)
