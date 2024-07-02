# -*- coding: utf-8 -*-

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import UserError
from uuid import uuid4


""" Cannot be edited by anyone, including admin"""
FORBIDDEN_FIELDS = {"reference"}

""" Cannot be edited by anyone else than trusted or admin"""
PROTECTED_FIELDS = {
    "name",
    "sequence",
    "picking_type_ids",
    "priority_group_ids",
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

    @api.multi
    @api.depends("reference")
    def _compute_pickings_count(self):
        """
        Count the number of transfers assigned to each priority.
        """
        for priority in self:
            Picking = self.env["stock.picking"]
            priority.picking_count = Picking.search_count(
                [
                    ("priority", "=", priority.reference),
                ]
            )

    def _default_sequence(self):
        max_rec = self.search([], order="sequence desc, id desc", limit=1)
        return max_rec.sequence + 1 if max_rec else 1

    sequence = fields.Integer(
        default=_default_sequence, help="Used to order the priorities"
    )
    description = fields.Text(help="A description about the purpose of the priority")
    picking_type_ids = fields.Many2many(
        "stock.picking.type",
        string="Stock Transfer Types",
        help="The stock transfer types this priority is visible on. No transfer types means all transfer types",
    )
    picking_count = fields.Integer(
        string="Affected Stock Transfers",
        compute="_compute_pickings_count",
        help="Stock transfers that would be affected by changes in the current priority.",
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
            raise UserError("Name must be unique for the transfer types it is shown on")

    @api.constrains("active")
    def _check_existing_transfers(self):
        """Constrain active field

        Allow only priorities with no existing stock transfers set to this priority to be archived.
        """
        inactive_priorities = self.filtered(lambda p: not p.active)
        for priority in inactive_priorities:
            if priority.picking_count:
                raise UserError(
                    "Cannot archive a priority that is set on existing transfers."
                )

    def _is_user_trusted_or_admin(self):
        return self.env.uid == SUPERUSER_ID or self.env.user.has_group(
            "udes_security.group_trusted_user"
        )

    def _is_install_mode(self):
        """Return true if Odoo is installing the module"""
        return self.env.context.get("install_mode", False)

    @api.multi
    def _validate_transfer_types_changes(self, values):
        """Validate changes to transfer types

        Allow addition of any transfer type but no removal of transfer types when
        there are existing transfers of this type with the current priority set.
        """
        if self._is_install_mode():
            return

        if "picking_type_ids" in values:
            Picking = self.env["stock.picking"]
            message = (
                "Invalid changes, you cannot remove the following transfer types as there are existing"
                " transfers from this type assigned to the current priority:\n"
            )
            invalid = False
            new_ids = values["picking_type_ids"][0][2]

            for old_pick_type in self.picking_type_ids:
                if old_pick_type.id not in new_ids:
                    assigned_pickings = Picking.search_count(
                        [
                            ("priority", "=", self.reference),
                            ("picking_type_id", "=", old_pick_type.id),
                        ]
                    )
                    if assigned_pickings:
                        invalid = True
                        message += "\n" + old_pick_type.name
            if invalid:
                raise UserError(message)

    @api.multi
    def propagate_sequence_to_pickings(self, sequence):
        """
        Propagate sequence changes to all relevant stock transfers with the current priority.
        Done and Cancelled transfers are excluded for audit traceability.
        """
        StockPicking = self.env["stock.picking"]
        for priority in self:
            pickings_to_update = StockPicking.search([
                ("priority", "=", priority.reference),
                ("state", "in", ["assigned", "confirmed", "draft", "waiting"])
            ])
            pickings_to_update.write({"u_priority_sequence": sequence})

    @api.multi
    def write(self, values):
        if any(k in FORBIDDEN_FIELDS for k in values):
            if self._is_install_mode():
                return
            raise UserError("Cannot change protected fields.")

        if self._is_user_trusted_or_admin():
            self._validate_transfer_types_changes(values)
        else:
            if any(k in PROTECTED_FIELDS for k in values):
                raise UserError("You do not have the rights for making changes.")
        if "sequence" in values:
            self.propagate_sequence_to_pickings(values["sequence"])
        return super().write(values)

    @api.multi
    def unlink(self):
        if self._is_user_trusted_or_admin() is False:
            raise UserError("You do not have the rights for making changes.")
        for priority in self:
            if priority.picking_count:
                raise UserError(
                    "Changes cannot be applied as there are transfers assigned to selected priorities."
                )
        return super().unlink()

    @api.multi
    def get_selection_values(self):
        return [(p.reference, _(p.name)) for p in self]
