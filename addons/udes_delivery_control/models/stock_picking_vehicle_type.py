from odoo import fields, models


class StockPickingVehicleType(models.Model):

    _name = "stock.picking.vehicle.type"
    _description = "UDES stock picking vehicle type"
    _order = "sequence, name"

    name = fields.Char(string="Vehicle Type", index=True)
    sequence = fields.Integer(help="Determine the display order")
