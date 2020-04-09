from odoo import models

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def get_action_picking_tree_draft(self):
        return self._get_action('udes_stock.action_picking_tree_draft')
