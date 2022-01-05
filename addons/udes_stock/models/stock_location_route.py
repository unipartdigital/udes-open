from odoo import fields, models


class Route(models.Model):
    _inherit = "stock.location.route"

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)
