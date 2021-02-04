from odoo import models, fields, api, _
from odoo.exceptions import UserError


class UdesPriorityGroup(models.Model):
    _name = "udes_priorities.priority_group"
    _order = "id"

    name = fields.Char()
    priority_ids = fields.Many2many(
        "udes_priorities.priority", column1="group_id", column2="priority_id", string="Priorities"
    )
    active = fields.Boolean(default=True)
    picking_type_ids = fields.Many2many(
        "stock.picking.type",
        string="Stock Transfer Types",
        help="The stock picking types this priority is visible on",
        compute="_compute_picking_types",
        store=True,
    )

    @api.multi
    @api.depends("priority_ids", "priority_ids.picking_type_ids")
    def _compute_picking_types(self):
        for group in self:
            group.picking_type_ids = group.mapped("priority_ids.picking_type_ids")

    @api.depends("picking_type_ids.active")
    def _deactivate_group(self):
        for group in self:
            if len(group.priority_ids) == 0:
                group.active = False

    @api.multi
    def copy(self, default=None):
        """Append '(copy)' to Name if not supplied"""
        if len(self) == 1:
            if default is None:
                default = {}

            if not default.get("name"):
                default["name"] = "%s (copy)" % self.name

        return super().copy(default)

    def _has_duplicate_names_for_same_pick_type(self):
        Group = self.env["udes_priorities.priority_group"]
        self.ensure_one()

        domain = [("name", "=", self.name), ("id", "!=", self.id)]

        if self.picking_type_ids:
            domain.extend(
                [
                    "|",
                    ("picking_type_ids", "in", self.picking_type_ids.ids),
                    ("picking_type_ids", "=", False),
                ]
            )
        return Group.search_count(domain)

    @api.constrains("name", "picking_type_ids")
    @api.depends("name", "picking_type_ids")
    @api.one
    def _check_for_duplicate_names_for_same_pick_type(self):
        if self._has_duplicate_names_for_same_pick_type() > 0:
            raise UserError("Name must be unique for the picking types it is shown on")
