from odoo import fields, models, _


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    u_so_auto_confirm_ahead_days = fields.Integer(
        "Auto Confirm sale order within (days)",
        default=1,
        help="Days ahead to auto confirm sales orders for. " "0 = Today, 1 = Tomorrow, -1 = All",
    )

    u_allow_manual_sale_order_line_cancellation = fields.Boolean(
        "Allow manual cancellation of individual sale order lines",
        default=False,
    )

    u_disallow_manual_sale_order_line_cancellation_at_picking_type_ids = fields.Many2many(
        comodel_name="stock.picking.type",
        relation="stock_warehouse_disallow_so_line_cancel_at_picking_types_rel",
        string="Disallow manual cancellation of sale order lines at these picking stages",
    )
