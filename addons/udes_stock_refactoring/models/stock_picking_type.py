# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_auto_unlink_empty = fields.Boolean(
        string="Auto Unlink Empty",
        default=True,
        help="""
        Flag to indicate whether to unlink empty pickings when searching for any empty picking in 
        the system.
        """,
    )

    # Picking lifecycle actions

    u_move_line_key_format = fields.Char(
        "Move Line Grouping Key",
        help="A field name on stock.move.line that can be used to group move lines.",
    )

    u_move_key_format = fields.Char(
        "Move Grouping Key", help="A field name on stock.move that can be to group move.",
    )

    # Actions are fetched on implementation from Refactor classes

    u_post_confirm_action = fields.Selection(
        selection=[],
        string="Post Confirm Action",
        help="Choose the action to be taken after confirming a picking.",
    )

    u_post_assign_action = fields.Selection(
        selection=[],
        string="Post Assign Action",
        help="Choose the action to be taken after reserving a picking.",
    )

    u_post_validate_action = fields.Selection(
        selection=[],
        string="Post Validate Action",
        help="Choose the action to be taken after validating a picking.",
    )
