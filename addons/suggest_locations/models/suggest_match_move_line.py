# -*- coding: utf-8 -*-
from odoo import models, fields, _

from .suggest_locations_policy import SuggestLocationPolicy, get_selection


class MatchMoveLine(SuggestLocationPolicy):
    """Match the value set on the move line"""

    @classmethod
    def name(cls):
        return "match_move_line"

    def get_values_from_mls(self, mls):
        return {"location": mls.location_dest_id.ensure_one()}

    def get_values_from_dict(self, values):
        picking_id = values.get("picking_id")
        if not picking_id:
            raise ValueError(_("No picking found"))

        location_dest_id = values.get("location_dest_id")
        if not location_dest_id:
            raise ValueError(_("No location found"))

        if isinstance(location_dest_id, int):
            location = self.env["stock.location"].browse(location_dest_id)
        elif isinstance(location_dest_id, models.BaseModel):
            location = location_dest_id.ensure_one()

        return {"location": location, "picking_id": self.env["stock.picking"].browse(picking_id)}

    def get_locations(self, location, **kwargs):
        return location

    def iter_mls(self, mls):
        for _loc_id, grouped_mls in mls.groupby("location_dest_id"):
            yield grouped_mls


class PickingType(models.Model):

    _inherit = "stock.picking.type"

    u_suggest_locations_policy = fields.Selection(selection_add=[get_selection(MatchMoveLine)])
