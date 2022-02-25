from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_num_reservable_pickings = fields.Integer(
        string="Number of Pickings to Reserve",
        default=0,
        help="The number of pickings in the queue to reserve stock for. "
        "If batch reservation is enabled, entire picking batches are "
        "reserved in the order of their earliest picking in the queue "
        "until at least this number of pickings are reserved. "
        "0 indicates no pickings should be reserved. "
        "-1 indicates all pickings should be reserved.",
    )

    u_reserve_batches = fields.Boolean(
        string="Reserve Picking Batches Atomically",
        default=False,
        help="Flag to indicate whether to reserve pickings by batches. "
        "This is ignored if the number of pickings to reserve is 0.",
    )
