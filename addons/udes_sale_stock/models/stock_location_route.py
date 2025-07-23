from odoo import api, fields, models, tools, _


class StockLocationRoute(models.Model):
    _inherit = "stock.location.route"

    u_pick_operation_type_ids = fields.Many2many(
        "stock.picking.type",
        "pick_operation_type_id",
        "pick_route_id",
        string="Pick Operation Types",
    )
    u_pack_operation_type_ids = fields.Many2many(
        "stock.picking.type",
        "pack_operation_type_id",
        "pack_route_id",
        string="Pack Operation Types",
    )
