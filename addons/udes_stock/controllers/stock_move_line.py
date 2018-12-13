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

        locations = None
        mls = MoveLine.browse(move_line_ids)

        for pick in mls.mapped('picking_id'):
            pick_mls = mls.filtered(lambda ml: ml.picking_id == pick)
            pick_loc = pick.get_suggested_locations(pick_mls)
            locations = pick_loc if locations is None \
                        else locations & pick_loc

        return locations.get_info()
