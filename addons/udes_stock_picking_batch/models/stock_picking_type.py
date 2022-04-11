from odoo import models, fields


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_auto_assign_batch_pick = fields.Boolean(
        string="Auto Assign Running Batch Picks",
        help="Reserve automatically stock to picks when added to a running batch",
        default=False,
    )

    u_remove_unready_batch = fields.Boolean(
        string="Auto Remove Running Batch Unready Picks",
        help="Remove automatically unready picks from a running batch when batch assigned or pick state changed",
        default=True,
    )
