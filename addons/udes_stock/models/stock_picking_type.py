from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_reserve_as_packages = fields.Boolean(
        string="Reserve entire packages",
        default=False,
        help="Flag to indicate reservations should be rounded up to entire packages.",
    )

    def get_action_picking_tree_draft(self):
        return self._get_action("udes_stock.action_picking_tree_draft")
