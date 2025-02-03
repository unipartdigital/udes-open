from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = "product.category"

    active = fields.Boolean(
        default=True, string="Active", help="Display in list views or searches."
    )
