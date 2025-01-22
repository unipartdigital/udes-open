from odoo import api, fields, models

RULE_RESERVATION_TYPE_WHOLE_PALLET = "whole_pallet"
# This would require a new column and additional logic, not in scope of SE-1721.
# RULE_RESERVATION_TYPE_QTY_COMPARISON = "qty_greaterthan"


RULE_RESERVATION_TYPES = [
    (RULE_RESERVATION_TYPE_WHOLE_PALLET, "Whole Pallet"),
]


class StockRule(models.Model):
    _inherit = "stock.rule"

    u_push_on_drop = fields.Boolean(
        "Push on Drop-off",
        default=False,
        help="When stock is dropped in the "
        "from_location of this path, "
        "automatically push it onwards.",
    )
    u_run_on_assign = fields.Boolean(
        "Run on assign",
        default=False,
        help="Do not run this rule from a procurement group. "
        "Instead run it on action_assign. Rules which have this flag set will "
        "be used during stock assignment. Stock will be looked up in the Source Location "
        "using the Reservation Type."
        "If any stock is found, it will be split to the Operation Type of this rule "
        "(if it differs from the 'is applicable to' type)."
        "Multiple rules can exist for the same applicable Operation Type. In these cases "
        "the system will iterate over the rules one by one, trying to reserve remaining stock "
        "using the 'current' rule.",
    )
    # Only shown if u_run_on_assign is set.
    u_run_on_assign_reservation_type = fields.Selection(
        string="Reservation Type",
        default=False,
        selection=RULE_RESERVATION_TYPES,
        help="Reservation strategy of the rule.\n"
        "- <Empty>: No additional reservation strategy will be used for this rule.\n"
        "- Whole Pallet: Only whole pallets will be considered to be assigned.",
    )
    # Only shown if u_run_on_assign is set.
    u_run_on_assign_applicable_to = fields.Many2one(
        string="Run on assign is applicable to",
        comodel_name="stock.picking.type",
        help="Picking types which this rule should be considered for.",
    )

    @api.model
    def get_path_from_location(self, location):
        """
        Find a single stock.rule for which the given location is
        a valid starting location. If one not found return an empty recordset.
        Search for the stock.rules attached to the parent locations of location. If there is more than one stock.rule in the location hierarchy,
        sort them by choosing the parent_path with the largest integer at the end of its path. This is the closest parent location to the input
        location and hence the most relevant stock.rule.
        Note: If there is more than one stock.rule defined on the closest location, the newest stock.rule on that location will be chosen.
        """
        Rule = self.env["stock.rule"]
        push_steps = Rule.search(
            [
                (
                    "location_src_id",
                    "parent_of",
                    [
                        location.id,
                    ],
                ),
                ("u_push_on_drop", "=", True),
            ]
        )
        if push_steps:
            to_order = push_steps.filtered(lambda p: p.location_src_id.parent_path)
            ordered_steps = to_order.sorted(
                key=lambda p: p.location_src_id.parent_path.strip("/").split("/")[-1], reverse=True
            )
            return ordered_steps[0] if ordered_steps else push_steps[0]
        return self.browse()

    def _run_push(self, move):
        """
        Odoo has default behaviour to create another picking after a move is confirmed. Don't want this functionality
        if u_push_on_drop is turned on.
        """
        if self.u_push_on_drop:
            return
        return super()._run_push(move)


    def _get_message_dict(self):
        """Extend _get_message_dict to generate a message for rules who have u_run_on_assign set"""
        res = super()._get_message_dict()
        # Update to consider u_run_on_assign so the UI message is not confusing.
        if self.u_run_on_assign:
            applicable = self.u_run_on_assign_applicable_to
            optype = self.picking_type_id
            reservation_type = self.selection_display_name("u_run_on_assign_reservation_type") or "No"
            message = f"""
                When stock is assigned on the <b>{applicable.name}</b> Operation Type,<br/>
                stock will be looked up in <b>{self.location_src_id.name}</b> at sequence <b>{self.sequence}</b>
                using <b>{reservation_type}</b> Reservation Type.<br/>
            """
            if applicable != optype:
                message += f"The reserved stock will be split to a <b>{optype.name}</b> Operation Type<br/>"
            res["run_on_assign"] = message
        return res

    @api.depends('action', 'location_id', 'location_src_id', 'picking_type_id', 'procure_method', 'u_run_on_assign', 'u_run_on_assign_applicable_to', 'u_run_on_assign_reservation_type')
    def _compute_action_message(self):
        """Extend _compute_action_message to set a message for rules who have u_run_on_assign set"""
        super()._compute_action_message()
        # Update to consider u_run_on_assign so the UI message is not confusing.
        run_on_assign_rules = self.filtered(lambda r: r.u_run_on_assign)
        for rule in run_on_assign_rules:
            message_dict = rule._get_message_dict()
            message = message_dict.get("run_on_assign")
            rule.rule_message = message
