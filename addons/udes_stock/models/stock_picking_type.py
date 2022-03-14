"""UDES core picking type functionality."""
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_auto_unlink_empty = fields.Boolean(
        string="Auto Unlink Empty",
        default=True,
        help="""
        Flag to indicate whether to unlink empty pickings when searching for any empty picking in
        the system.
        """,
    )

    def get_action_picking_tree_draft(self):
        return self._get_action("udes_stock.action_picking_tree_draft")
