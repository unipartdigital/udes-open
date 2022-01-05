# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError


class StockWarehouse(models.Model):
    _name = "stock.warehouse"
    _inherit = ["stock.warehouse", "mail.thread"]

    # Add tracking for archiving.
    active = fields.Boolean(tracking=True)

    def get_picking_types(self):
        """Returns a recordset with the picking_types of the warehouse"""
        PickingType = self.env["stock.picking.type"]

        self.ensure_one()
        # get picking types of the warehouse
        picking_types = PickingType.search([("warehouse_id", "=", self.id)])
        if not picking_types:
            raise ValidationError(_("Cannot find picking types for warehouse %s.") % self.name)

        return picking_types
