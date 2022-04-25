from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    u_log_batch_picking = fields.Boolean(
        string="Log Batch Picking",
        default=False,
        help="Logs details when picking is added to batch picking",
    )
