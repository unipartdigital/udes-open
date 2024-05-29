from odoo import fields, models, api, _
from collections import defaultdict, OrderedDict

# N.B. Custom field.
from ..fields import Integer


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.model
    def _default_priority(self):
        return self.env.ref("udes_priorities.normal").reference

    priority = fields.Selection(selection="get_priorities_for_selection", default=_default_priority)
    u_priority_id = fields.Many2one(
        comodel_name="udes_priorities.priority", compute="_compute_priority_id", store=True
    )
    u_priority_sequence = Integer(
        string="Priority Sequence", compute="_compute_priority_sequence", store=True
    )

    def _priority_and_priority_group_domain(self, picking_type_ids=None):
        domain = []
        if picking_type_ids is None:
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
                    ("picking_type_ids", "=", False),  # No picking types means all picking types
                ]
            )

        return domain

    def _priority_domain(self, picking_type_ids=None):
        # _priority_domain and _priority_group_domain may diverge in certain circumstances
        # To allow for this they are proxies to the default function
        return self._priority_and_priority_group_domain(picking_type_ids=picking_type_ids)

    def _priority_group_domain(self, picking_type_ids=None):
        # _priority_domain and _priority_group_domain may diverge in certain circumstances
        # To allow for this they are proxies to the default function
        return self._priority_and_priority_group_domain(picking_type_ids=picking_type_ids)

    @api.depends('priority')
    def _compute_priority_id(self):
        Priorities = self.env["udes_priorities.priority"]

        for record in self:
            priority = Priorities.search([('reference', '=', record.priority)])
            record.u_priority_id = priority

    @api.depends("u_priority_id.sequence")
    def _compute_priority_sequence(self):
        """Set the sequence associated with a picking's priority."""
        for record in self.filtered(lambda r: r.state not in ["cancel", "done"]):
            record.u_priority_sequence = record.u_priority_id.sequence

    @api.model
    def get_priorities_for_selection(self):
        Priorities = self.env["udes_priorities.priority"]
        pick_id = self.env.context.get("id", None)
        picks = self
        if not picks and pick_id:
            active_pick = self.browse(pick_id).exists()
            if active_pick:
                picks = active_pick

        priorities = Priorities.search(picks._priority_domain())

        # hard coded default value means there is always a priority to set
        normal = self.env.ref("udes_priorities.normal")
        priorities |= normal
        # Fail gracefully if some how the priority is something it shouldn't be allowed then
        # add it so everything doesn't explode
        pick_priorities = Priorities.search([("reference", "in", picks.mapped("priority"))])
        return (priorities | pick_priorities).get_selection_values()

    @api.model
    def get_priorities(self, picking_type_id=None):
        """ Return a list of dicts containing the priorities of
            all defined priority groups, in the following format:
                [
                    {
                        'name': 'Picking',
                        'priorities': [
                            {'id': '2', 'name': 'Urgent'},
                            {'id': '1', 'name': 'Normal'}
                        ]
                    },
                    {
                        ...
                    },
                    ...
                ]
        """
        PriorityGroup = self.env["udes_priorities.priority_group"]
        groups = []

        group_domain_kwargs = {}
        if picking_type_id is not None:
            group_domain_kwargs["picking_type_ids"] = [picking_type_id]

        for group in PriorityGroup.search(self._priority_group_domain(**group_domain_kwargs)):
            priorities = group.priority_ids.mapped("reference")
            if picking_type_id is None or self._priorities_has_ready_pickings(
                priorities, picking_type_id
            ):
                groups.append(
                    {
                        "name": group.name,
                        "priorities": [
                            {"id": p.reference, "name": p.name} for p in group.priority_ids
                        ],
                    }
                )
        return groups

    def _prepare_info(self, priorities=None, fields_to_fetch=None):
        if not priorities:
            priorities = OrderedDict(self.get_priorities_for_selection())
        return super()._prepare_info(priorities=priorities, fields_to_fetch=fields_to_fetch)

    def get_info(self, **kwargs):
        """ Return a list with the information of each picking in self.
        """
        return [p._prepare_info(**kwargs) for p in self]

    def _get_priority_name(self):
        self.ensure_one()
        Priorities = self.env["udes_priorities.priority"]
        priority = Priorities.search([("reference", "=", self.priority)])
        return priority.name

    def get_picking_guidance(self):
        """ Return dict of guidance info to aid user when picking """
        return {"Priorities": self._get_priority_name()}

    @api.one
    @api.depends("move_lines.priority")
    def _compute_priority(self):
        """Override to select the correct priority"""
        Priorities = self.env["udes_priorities.priority"]
        if self.mapped("move_lines") and not isinstance(self.id, models.NewId):
            priority = Priorities.search(
                [("reference", "in", self.mapped("move_lines.priority"))],
                limit=1,  # Assume _order is "highest" priority first
            )
            picking_type_priorities = Priorities.search(
                self._priority_and_priority_group_domain(self.picking_type_id.id)
            )
            if priority in picking_type_priorities | self.env.ref("udes_priorities.normal"):
                self.priority = priority.reference
            else:
                raise ValueError(
                    "Priority of move (priority: '%s') not in allowed priorities for picking '%s'.",
                    priority.name,
                    picking_type_priorities.mapped("name"),
                )
        else:
            self.priority = self._default_priority()

    @api.constrains("priority")
    @api.onchange("priority")
    def _priority_cant_be_empty(self):
        for pick in self:
            if not pick.priority:
                pick.priority = self.env.ref("udes_priorities.normal").reference

    @api.model
    def create(self, values):
        Priority = self.env["udes_priorities.priority"]

        context = {}
        picking_type_id = values.get("picking_type_id", None)
        if picking_type_id:
            context = {"default_picking_type_id": picking_type_id}
        res = super(StockPicking, self.with_context(**context)).create(values)
        return res
