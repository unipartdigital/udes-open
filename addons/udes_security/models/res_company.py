from odoo import models, fields, _


class ResCompany(models.Model):
    _inherit = "res.company"

    u_minimum_password_length = fields.Integer(
        "Characters", default=14, help="Minimum password length"
    )
    u_minimum_password_lower = fields.Integer(
        "Lowercase", default=1, help="Minimum number of lowercase characters"
    )
    u_minimum_password_upper = fields.Integer(
        "Uppercase", default=1, help="Minimum number of uppercase characters"
    )
    u_minimum_password_numeric = fields.Integer(
        "Numeric", default=1, help="Minimum number of numeric digits"
    )
    u_minimum_password_special = fields.Integer(
        "Special", default=1, help="Minimum number of unique special characters"
    )
