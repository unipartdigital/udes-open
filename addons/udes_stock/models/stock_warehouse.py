from odoo import fields, models, _
from odoo.exceptions import ValidationError


class StockWarehouse(models.Model):
    _name = "stock.warehouse"
    _inherit = ["stock.warehouse", "mail.thread"]

    def _domain_u_damaged_location_id(self):
        """
        Domain for locations outside Stock
        """
        return ["!", ("id", "child_of", self.env.ref("stock.stock_location_stock").id)]

    # Add tracking for archiving.
    active = fields.Boolean(tracking=True)
    u_damaged_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Default Damaged Location",
        domain=_domain_u_damaged_location_id,
        help="The damaged location is a location outside Stock (it cannot be a"
        " location under Stock/), because we do not want damaged stock to"
        " be picked",
    )
    u_good_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Default Goods Location",
        help="Goods receive location used by mobile client",
    )
    u_pi_count_move_picking_type = fields.Many2one(
        comodel_name="stock.picking.type",
        string="PI Count Picking Type",
        help="Picking type used to create PI Count move pickings.",
    )

    u_damaged_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Default Damage Location",
        help="The damaged location is a location outside Stock (it cannot be a"
        " location under Stock/), because we do not want damaged stock to"
        " be picked",
    )
    u_good_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Default Goods Location",
        help="Goods receive location used by mobile client",
    )

    def get_picking_types(self):
        """Returns a recordset with the picking_types of the warehouse"""
        PickingType = self.env["stock.picking.type"]

        self.ensure_one()
        # get picking types of the warehouse
        picking_types = PickingType.search([("warehouse_id", "=", self.id)])
        if not picking_types:
            raise ValidationError(_("Cannot find picking types for warehouse %s.") % self.name)

        return picking_types
