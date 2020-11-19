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

        priorities = Priorities.search(pick._priority_domain())

        # hard coded default value means there is always a priority to set
        normal = self.env.ref("udes_priorities.normal")
        priorities |= normal

        for batch in self.filtered(lambda b: b.priority not in priorities):
            # Theres some race conditions around where data is aviable to search on this means
            # that sometimes an invalid default can be set
            batch.priority = normal.reference

        return priorities.get_selection_values()

    @api.constrains("priority")
    @api.depends("priority")
    @api.onchange("priority")
    def _priority_cant_be_empty(self):
        for batch in self:
            if not batch.priority:
                batch.priority = self.env.ref("udes_priorities.normal").reference
