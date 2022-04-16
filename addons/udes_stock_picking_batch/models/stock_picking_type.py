from odoo import models, fields


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_auto_assign_batch_pick = fields.Boolean(
        string="Auto assign picks when added to a running batch",
        help="Auto assign picks when added to a running batch",
        default=False,
    )

    u_remove_unready_batch = fields.Boolean(
        string="Auto remove unready picks from a running batch",
        help="Auto remove unready picks from a running batch on assign",
        default=True,
    )
