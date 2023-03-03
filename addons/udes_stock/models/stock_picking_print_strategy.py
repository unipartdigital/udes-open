# -*- coding: utf-8 -*-

"""Print Strategy for stock picking."""

from odoo import api, fields, models


class PrintStrategy(models.Model):
    """Print strategies for stock picking by picking type."""

    _name = "udes_stock.stock.picking.print.strategy"
    _inherit = "print.strategy"

    # the picking type to which this print strategy applies
    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Picking Type",
        required=True,
    )
    action_filter = fields.Char("Action Filter", readonly=False, index=True)

    @api.model
    def strategies(self, picking):
        """Return print strategies for the picking type of `picking`."""
        picking.ensure_one()
        action_filter = self.env.context.get("action_filter")
        domain = [("picking_type_id", "=", picking.picking_type_id.id)]

        if action_filter is not None:
            domain.append(("action_filter", "=", action_filter))

        return self.search(domain)

    def records(self, picking, context):
        """Return records to print for `report`."""
        picking.ensure_one()
        print_records = context.get("print_records")

        if print_records is not None and self.model == print_records._name:
            return print_records
        elif self.model == picking._name:
            return picking
        return None
