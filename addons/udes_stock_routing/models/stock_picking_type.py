from odoo import models, fields

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_ignore_two_stage = fields.Boolean(
        string="Ignore Two Stage Split",
        default=False,
        help="If enabled, pickings of this type will skip two-stage routing.",
    )
