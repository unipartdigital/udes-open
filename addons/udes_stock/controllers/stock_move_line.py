# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi

class StockMoveLineApi(UdesApi):

    @http.route('/api/stock-move-line/suggested-locations',
                type='json', methods=['GET'], auth='user')
    def suggested_locations(self, move_line_ids):
        """
        Search suggested locations - refer to the API specs for details.
        """
        MoveLine = request.env['stock.move.line']

        if not move_line_ids:
            raise ValidationError(_("Must specify the 'move_line_ids' entry"))

        response = []
        locations = None
        empty_locations = None
        mls = MoveLine.browse(move_line_ids)

        for pick in mls.mapped('picking_id'):
            pick_mls = mls.filtered(lambda ml: ml.picking_id == pick)
            pick_locs = pick.get_suggested_locations(pick_mls)
            locations = pick_locs if locations is None \
                        else locations & pick_locs

            if pick.picking_type_id.u_drop_location_constraint == "enforce_with_empty":
                pick_empty_locs = pick.get_empty_locations()
                empty_locations = pick_empty_locs if empty_locations is None \
                                  else empty_locations & pick_empty_locs

        if locations:
            response.append({"title": "",
                             "locations": locations.get_info()})

            if empty_locations:
                # Ensure we don't have duplicates in the two recordsets
                empty_locations = empty_locations - locations

        if empty_locations:
            response.append({"title": "empty",
                             "locations": empty_locations.get_info()})

        return response
