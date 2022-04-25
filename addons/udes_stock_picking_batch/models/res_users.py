from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ResUser(models.Model):
    _inherit = "res.users"

    u_location_category_ids = fields.Many2many(
        comodel_name="stock.location.category", index=True, string="Location Category"
    )

    def get_user_location_categories(self):
        """Get the location categories of the user"""
        user = self.search([("id", "=", self.env.uid)])
        if not user:
            raise ValidationError(_("Cannot find user to get location categories."))

        return user.u_location_category_ids
