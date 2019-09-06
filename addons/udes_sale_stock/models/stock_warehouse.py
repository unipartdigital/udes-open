from odoo import fields, models, _


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    u_so_auto_confirm_ahead_days = fields.Integer(
        "Auto Confirm sale order within (days)",
        default=-1,
        help="Days ahead to auto confirm sales orders for. "
             "0 = Today, 1 = Tomorrow, -1 = All"
    )
