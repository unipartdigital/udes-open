# -*- coding: utf-8 -*-
from itertools import groupby

from odoo import models, fields, _

from .refactor import Refactor, get_selection


class BatchPickingsByDate(Refactor):
    """Refactor pickings by scheduled date."""

    @classmethod
    def name(cls):
        """Set code name of the refactor action."""
        return "batch_pickings_by_date"

    @classmethod
    def description(cls):
        """Set description of the refactor action."""
        return "Batch Pickings by Date"

    def do_refactor(self, moves):
        """Batch pickings by date."""
        moves._refactor_action_batch_pickings_by(
            lambda picking: (picking.scheduled_date.strftime("%Y-%m-%d"))
        )


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_post_confirm_action = fields.Selection(selection_add=[get_selection(BatchPickingsByDate)])
