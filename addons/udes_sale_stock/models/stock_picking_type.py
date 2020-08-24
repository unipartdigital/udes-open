from odoo import fields, models

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_warn_picking_precondition = fields.Selection(
        selection_add=[
            ("any_previous_pickings_not_complete_sale",
             "Any pickings from previous stages on the Sale Order not complete"),
        ]
    )
