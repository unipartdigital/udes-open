# -*- coding: utf-8 -*-
from odoo import models, fields, _

from .suggest_locations_policy import SuggestLocationPolicy, get_selection


class MatchMoveLine(SuggestLocationPolicy):
    """Match the value set on the move line"""

    preprocessing = True

    @classmethod
    def name(cls):
        return "match_move_line"

    def get_values_from_mls(self, mls):
        return {"location": mls.location_dest_id.ensure_one()}

    def _get_location_from_dict(self, values):
        """Get the location from the values, assumed ot be the int id of a location"""
        Location = self.env["stock.location"]
        location_dest_id = values.get("location_dest_id")
        if not location_dest_id:
            raise ValueError(_("No location found"))
        return Location.browse(location_dest_id)

    def get_values_from_dict(self, values):
        return {"location": self._get_location_from_dict(values)}

    def get_locations(self, location, **kwargs):
        return location

    def iter_mls(self, mls):
        for _loc_id, grouped_mls in mls.groupby("location_dest_id"):
            yield grouped_mls


class PickingType(models.Model):

    _inherit = "stock.picking.type"

    u_suggest_locations_policy = fields.Selection(selection_add=[get_selection(MatchMoveLine)])
