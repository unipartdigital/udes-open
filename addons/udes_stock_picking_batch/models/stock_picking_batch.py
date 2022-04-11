from odoo import models, fields


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    u_last_reserved_pallet_name = fields.Char(
        string="Last Pallet Used",
        index=True,
        help="Barcode of the last pallet used for this batch. "
             "If the batch is in progress, indicates the pallet currently in "
             "use.",
    )
