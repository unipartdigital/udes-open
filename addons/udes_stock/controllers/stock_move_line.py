# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi


class StockMoveLineApi(UdesApi):

    @staticmethod
    def get_suggested_locations(move_line_ids, limit=None, sort=False):
        MoveLine = request.env['stock.move.line']
        if not move_line_ids:
            raise ValidationError(_("Must specify the 'move_line_ids' entry"))

        locations = None
        empty_locations = None
        mls = MoveLine.browse(move_line_ids)

        for pick in mls.mapped('picking_id'):
            pick_mls = mls.filtered(lambda ml: ml.picking_id == pick)
            pick_locs = pick.get_suggested_locations(pick_mls, limit=limit, sort=sort)

            locations = pick_locs if locations is None \
                else locations & pick_locs

            if pick.picking_type_id.u_drop_location_constraint == "enforce_with_empty":
                pick_empty_locs = pick.get_empty_locations(limit=limit, sort=sort)
                empty_locations = pick_empty_locs if empty_locations is None \
                    else empty_locations & pick_empty_locs

        return locations, empty_locations

    @http.route('/api/stock-move-line/suggested-locations',
                type='json', methods=['POST'], auth='user')
    def suggested_locations(self, move_line_ids):
        """
        Search suggested locations - refer to the API specs for details.
        """
        response = []
        locations, empty_locations = self.get_suggested_locations(move_line_ids, limit=50, sort=True)

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

    @http.route('/api/stock-move-line/validate-location',
                type='json', methods=['POST'], auth='user')
    def validate_location(self, move_line_ids, location_barcode):
        """
        Validate Suggested Locations
        """
        Location = request.env['stock.location']
        location = Location.search([('barcode', '=', location_barcode)])
        location.ensure_one()
        if not location:
            raise ValidationError(_("Location not found"))
        locations, empty_locations = self.get_suggested_locations(move_line_ids, limit=None, sort=False)
        all_locations = locations | empty_locations
        if location not in all_locations:
            raise ValidationError(_("This is not an expected location"))
        info = location.get_info()[0]
        return info
