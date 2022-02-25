from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_reserve_as_packages = fields.Boolean(
        string="Reserve Entire Packages",
        default=False,
        help="Flag to indicate reservations should be rounded up to entire packages.",
    )
