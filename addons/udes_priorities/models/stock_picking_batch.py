# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    priority = fields.Selection(selection="get_priorities_for_selection")

    def _get_priority_name(self):
        self.ensure_one()
        Priorities = self.env["udes_priorities.priority"]
        priority = Priorities.search([("reference", "=", self.priority)])
        return priority.name

    def _priority_domain(self):
        domain = []
        picking_types = self.mapped("picking_type_ids")
        if picking_types:
            domain.append(("picking_type_ids", "in", picking_types.ids))
        return domain

    @api.model
    def get_priorities_for_selection(self):
        Priorities = self.env["udes_priorities.priority"]
        active_id = self.env.context.get("active_id", None)
        pick = self
        if active_id:
            active_pick = self.browse(active_id).exists()
            if active_pick:
                pick = active_pick
        return Priorities.search(pick._priority_domain()).get_selection_values()
