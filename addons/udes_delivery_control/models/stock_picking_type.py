from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_is_delivery_control = fields.Boolean("Is Delivery Control?", default=False)
