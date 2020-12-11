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
    @tools.ormcache()
    def get_priorities_for_selection(self):
        Priorities = self.env["udes_priorities.priority"]
        batch_id = self.env.context.get("id", None)
        batch = self
        if batch_id:
            active_batch = self.browse(batch_id).exists()
            if active_batch:
                batch = active_batch

        priorities = Priorities.search(batch._priority_domain())

        # hard coded default value means there is always a priority to set
        normal = self.env.ref("udes_priorities.normal")
        priorities |= normal

        # Fail gracefully if some how the priority is something it shouldn't be allowed then
        # add it so everything doesn't explode
        batch_priorities = Priorities.search([("reference", "in", batch.mapped("priority"))])
        return (priorities | batch_priorities).get_selection_values()

    @api.constrains("priority")
    @api.onchange("priority")
    def _priority_cant_be_empty(self):
        for batch in self:
            if not batch.priority:
                batch.priority = self.env.ref("udes_priorities.normal").reference
