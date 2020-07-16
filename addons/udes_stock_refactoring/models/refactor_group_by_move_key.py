# -*- coding: utf-8 -*-
from itertools import groupby

from odoo import models, fields, _

from .refactor import Refactor, get_selection


class GroupByMoveKey(Refactor):
    """
    Group the moves by the splitting criteria.
    For each resulting group of stock moves:
        - Create a new picking
        - Attach the moves to the new picking
    """

    @classmethod
    def name(cls):
        """Set code name of the refactor action."""
        return "group_by_move_key"

    @classmethod
    def description(cls):
        """Set description of the refactor action."""
        return "Group by Move Key"

    def do_refactor(self, moves):
        """
        Ensure that move records only have 1 picking type.
        If a move key format is set carry out the refactor
        by move groups.
        """
        picking_type = moves.picking_type_id
        picking_type.ensure_one()

        if not picking_type.u_move_key_format:
            return

        group_by_key = moves.group_by_key()

        return moves.refactor_by_move_groups(group_by_key)


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_post_confirm_action = fields.Selection(selection_add=[get_selection(GroupByMoveKey)])
    u_post_assign_action = fields.Selection(selection_add=[get_selection(GroupByMoveKey)])
    u_post_validate_action = fields.Selection(selection_add=[get_selection(GroupByMoveKey)])
