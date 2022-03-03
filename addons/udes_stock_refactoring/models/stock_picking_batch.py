from odoo import fields, models, api


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    @api.depends("picking_ids", "picking_ids.picking_type_id")
    def _compute_picking_type_ids(self):
        """Compute the picking types from the linked pickings"""
        for batch in self:
            if batch.picking_ids:
                batch.picking_type_ids = batch.picking_ids.picking_type_id
            else:
                batch.picking_type_ids = False

    picking_type_ids = fields.Many2many(
        "stock.picking.type",
        string="Operation Types",
        compute="_compute_picking_type_ids",
        store=True,
        index=True,
    )
