from odoo import fields, models, api, _


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.model
    def _default_priority(self):
        Priorities = self.env["udes_priorities.priority"]
        priorities = Priorities.search(self._priority_domain(), limit=1)
        return (
            priorities.reference if priorities else self.env.ref("udes_priorities.normal").reference
        )

    priority = fields.Selection(selection="get_priorities_for_selection", default=_default_priority)

    def _priority_domain(self):
        domain = []
        picking_type_ids = []

        picking_types = self.mapped("picking_type_id")
        default_picking_type_id = self.env.context.get("default_picking_type_id", None)

        if picking_types:
            picking_type_ids = picking_types.ids
        elif default_picking_type_id:
            picking_type_ids = [default_picking_type_id]

        if picking_type_ids:
            domain.extend(
                [
                    "|",
                    ("picking_type_ids", "in", picking_type_ids),
                    ("picking_type_ids", "=", False),
                ]
            )

        return domain

    @api.model
    def get_priorities_for_selection(self):
        Priorities = self.env["udes_priorities.priority"]
        priorities = Priorities.search(self._priority_domain())

        # hard coded default value means there is always a priority to set
        normal = self.env.ref("udes_priorities.normal")
        priorities |= normal

        if self and self.priority not in priorities:
            # Theres some race conditions around where data is aviable to search on this means
            # that sometimes an invalid default can be set
            self.priority = normal.reference

        return priorities.get_selection_values()

    @api.constrains("priority")
    @api.depends("priority")
    @api.onchange("priority")
    def _priority_cant_be_empty(self):
        for move in self:
            if not move.priority:
                move.priority = self.env.ref("udes_priorities.normal").reference
