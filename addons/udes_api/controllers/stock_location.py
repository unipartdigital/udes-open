# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from .main import UdesApi
from odoo.exceptions import ValidationError

class Location(UdesApi):

    @http.route('/api/stock-location/', type='json', methods=['GET'], auth='user')
    def get_location(self, id=None, query=None, load_quants=False):
        """
            @param: load_quants - (optional, default = false) Load the quants associated with a location.
            @param: id - (optional) the location's id
            @param query - (optional) this is a string that entirely matches either the name or barcode
            @return stock.location (as described above, containing the quants in the format also listed above).
        """
        Location = request.env['stock.location']
        identifier = id or query
        if not identifier:
            raise ValidationError(_('You need to provide an id or name for the location.'))

        location = Location.get_location(identifier)

        return location.get_info(extended=True, load_quants=load_quants)
