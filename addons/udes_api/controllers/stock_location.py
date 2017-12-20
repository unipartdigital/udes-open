# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from .main import UdesApi
from odoo.exceptions import ValidationError

class Location(UdesApi):

    @http.route('/api/stock-location/', type='json', methods=['GET'], auth='user')
    def get_location(self, id=None, query=None, load_quants=False):
        """ Search for a location by id or name/barcode and returns a
            stock.location object that match the given criteria.

            @param (optional) id
                The location's id
            @param (optional) query
                This is a string that entirely matches either the name or barcode
            @param (optional) load_quants: Boolean (default = false)
                Load the quants associated with a location.
        """
        Location = request.env['stock.location']
        identifier = id or query
        if not identifier:
            raise ValidationError(_('You need to provide an id or name for the location.'))

        location = Location.get_location(identifier)

        return location.get_info(extended=True, load_quants=load_quants)[0]
