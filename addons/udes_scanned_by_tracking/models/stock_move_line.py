# # -*- coding: utf-8 -*-

from odoo import api, models, fields, tools, _
from datetime import datetime

import logging

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    u_done_by = fields.Many2one(
        "res.users", "Scanned by", help="ID of the user to complete the pack op.", index=True
    )

    u_done_datetime = fields.Datetime(
        "Completion datetime", help="Date and time the operation was completed.", index=True
    )

    @staticmethod
    def _now_for_tracking_data():
        """Can be overwritten to change the tracking resolution"""
        return datetime.now()

    @api.model
    def _add_user_tracking_data(self, vals):
        """Inject/overwrite user tracking data into vals"""

        if vals.get("qty_done", 0) > 0:
            if not self.env.real_uid:  # real_uid is expected to be added within odoo core
                _logger.warning(
                    "env.real_uid is falsey (it's %s); we'll use env.uid (%s) for tracking "
                    "u_done_by for the move line '%s'",
                    self.env.real_uid,
                    self.env.uid,
                    self.id,
                )
                vals["u_done_by"] = self.env.uid
            else:
                vals["u_done_by"] = self.env.real_uid
            vals["u_done_datetime"] = self._now_for_tracking_data()
        return vals

    @api.model
    def create(self, vals):
        """Extend to track the requester user"""
        vals = self._add_user_tracking_data(vals)
        return super().create(vals)

    @api.model
    def write(self, vals):
        """Extend to track the requester user"""
        vals = self._add_user_tracking_data(vals)
        return super().write(vals)
