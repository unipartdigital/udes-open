from odoo import fields, models, _


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    u_log_batch_picking = fields.Boolean(
        string=_("Log Batch Picking"),
        default=False,
        help=_("Logs details when picking is added to batch picking"),
    )
