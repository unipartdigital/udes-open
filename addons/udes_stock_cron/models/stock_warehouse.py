from odoo import models, fields


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    u_one_product_per_location = fields.Boolean(
        "One Product Per Location",
        default=False,
        help="Flag to enable a check and raise an error if a location is found with a different product"
        " then mentioned in the replenishment rule while executing check order point cron",
    )
