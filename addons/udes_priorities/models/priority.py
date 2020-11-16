# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from uuid import uuid4

PROTECTED_FIELDS = {
    "name",
    "reference",
    "sequence",
    "picking_type_ids",
    "group_ids",
    "active",
}


class UdesPriority(models.Model):
    _name = "udes_priorities.priority"
    _order = "sequence,id"

    name = fields.Char(required=True)
    reference = fields.Char(
        help="Unique identifier for the priority",
        required=True,
        copy=False,
        default=lambda self: uuid4(),
    )

    def _default_sequence(self):
        max_rec = self.search([], order="sequence desc, id desc", limit=1)
        return max_rec.sequence + 1 if max_rec else 1

    sequence = fields.Integer(default=_default_sequence, help="Used to order the priorities")
    description = fields.Text(help="A description about the purpose of the priority")
    picking_type_ids = fields.Many2many(
        "stock.picking.type",
        string="Stock Transfer Types",
        help="The stock picking types this priority is visible on. No picking types means all picking types",
    )
    priority_group_ids = fields.Many2many(
        "udes_priorities.priority_group",
        store=True,
        column1="priority_id",
        column2="group_id",
        help="Priority groups are the priorities shown on the hand held terminal",
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("priority_reference_unique", "unique(reference)", "reference must be unique")
    ]

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
        Priority = self.env["udes_priorities.priority"]
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
        return Priority.search_count(domain)

    @api.constrains("name", "picking_type_ids")
    @api.depends("name", "picking_type_ids")
    @api.one
    def _check_for_duplicate_names_for_same_pick_type(self):
        if self._has_duplicate_names_for_same_pick_type() > 0:
            raise UserError("Name must be unique for the picking types it is shown on")

    @api.multi
    def _number_of_oustanding_pickings(self):
        Picking = self.env["stock.picking"]
        self.ensure_one()
        return Picking.search_count(
            [("priority", "=", self.reference), ("state", "not in", ("cancel", "done")),]
        )

    @api.multi
    def _check_for_oustanding_pickings(self):
        priorities_with_outstanding_picks = self.browse()
        for priority in self:
            if priority._number_of_oustanding_pickings() > 0:
                priorities_with_outstanding_picks |= priority

        if priorities_with_outstanding_picks:
            raise UserError(
                _("There are outstanding pickings for priorities: {}").format(
                    ", ".join(priorities_with_outstanding_picks.mapped("name"))
                )
            )

    @api.multi
    def write(self, values):
        if values and any(k in PROTECTED_FIELDS for k in values):
            self._check_for_oustanding_pickings()
        return super().write(values)

    @api.multi
    def unlink(self):
        self._check_for_oustanding_pickings()
        return super().unlink()

    @api.multi
    def get_selection_values(self):
        return [(p.reference, _(p.name)) for p in self]
