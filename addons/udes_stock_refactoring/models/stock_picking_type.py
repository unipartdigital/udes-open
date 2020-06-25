# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


U_STOCK_REFACTORING_CORE_LIFECYCLE_ACTIONS = [
    ("group_by_move_line_key", "Group by Move Line Key"),
    ("group_by_move_key", "Group by Move Key"),
]


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    # Picking lifecycle actions

    u_move_line_key_format = fields.Char(
        "Move Line Grouping Key",
        help="""A field name on stock.move.line that can be used to group
        move lines.""",
    )

    u_move_key_format = fields.Char(
        "Move Grouping Key", help="""A field name on stock.move that can be to group move.""",
    )

    u_post_confirm_action = fields.Selection(
        selection=[
            ("group_by_move_key", "Group by Move Key"),
            ("batch_pickings_by_date", "Batch pickings by date"),
            ("batch_pickings_by_date_priority", "Batch pickings by date and priority"),
        ],
        string="Post Confirm Action",
        help="Choose the action to be taken after confirming a picking.",
    )

    u_post_assign_action = fields.Selection(
        selection=U_STOCK_REFACTORING_CORE_LIFECYCLE_ACTIONS,
        string="Post Assign Action",
        help="Choose the action to be taken after reserving a picking.",
    )

    u_post_validate_action = fields.Selection(
        selection=U_STOCK_REFACTORING_CORE_LIFECYCLE_ACTIONS,
        string="Post Validate Action",
        help="Choose the action to be taken after validating a picking.",
    )

    def do_refactor_action(self, action, moves):
        """Resolve and call the method to be executed on the moves.

           Methods doing a refactor are expected to take a single recordset of
           moves on which they will act, and to return the recordset of
           equivalent moves after they have been transformed.
           The output moves may be identical to the input, may contain none
           of the input moves, or anywhere in between.
           The output should contain a functionally similar set of moves.
        """
        Move = self.env["stock.move"]
        if action == "none":
            return moves

        # TODO: getattr(self will return a func bound to self, then just func()
        func = getattr(Move, "refactor_action_" + action, None)
        if func is not None:
            return func(moves)
        return moves
