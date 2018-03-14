# -*- coding: utf-8 -*-

import json
import os

import jsonschema

from odoo import http, _
from odoo.http import request as odoo_http_request
from .main import UdesApi
from odoo.exceptions import ValidationError


PIRequestValidator = None
SCHEMA_FILE_REL_PATH = '../schemas/stock-location-pi-count.json'


def _validate_pi_request(request):
    """ Raises a ValidationError for invalid request """
    global PIRequestValidator

    if PIRequestValidator is None:
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.abspath(
            os.path.join(tests_dir, SCHEMA_FILE_REL_PATH))

        with open(schema_path, 'r') as f_r:
            request_schema = json.loads(f_r.read())
            PIRequestValidator = jsonschema.Draft4Validator(request_schema)

    return PIRequestValidator.is_valid(request)


class Location(UdesApi):

    @http.route('/api/stock-location/', type='json', methods=['GET'], auth='user')
    def get_location(self, location_id=None, location_name=None,
                     location_barcode=None, load_quants=False, check_blocked=False):
        """ Search for a location by id, name or barcode and returns a
            stock.location object that match the given criteria.

            @param (optional) location_id
                The location's id
            @param (optional) location_name
                This is a string that entirely matches the name
            @param (optional) location_barcode
                This is a string that entirely matches the barcode
            @param (optional) load_quants: Boolean (default = false)
                Load the quants associated with a location.
            @param (optional) check_blocked:  Boolean (default = false)
                When enabled, checks if the location is blocked, in which case
                an error will be raise.
        """
        Location = odoo_http_request.env['stock.location']
        identifier = location_id or location_name or location_barcode
        if not identifier:
            raise ValidationError(
                _('You need to provide an id, name or barcode for the location.'))

        location = Location.get_location(identifier)

        if check_blocked:
            location.check_blocked()

        return location.get_info(extended=True, load_quants=load_quants)[0]

    @http.route('/api/stock-location-pi-count/',
                type='json', methods='POST', auth='user')
    def pi_count(self, request):
        """
            Process a Perpetual Inventory (PI) count request.

            Raises a ValidationError in case of invalid request or if
            any of the specified location is unknown.

            @param req is a JSON object with the "pi_count_moves",
            "inventory_adjustments", "preceding_inventory_adjustments"
            and "location_id" entries
        """
        Location = odoo_http_request.env['stock.location']

        _validate_pi_request(request)
        location_id = None

        try:
            # @todo: check if UI is passing strings for numbers...
            location_id = int(request.get('location_id'))
        except ValueError:
            pass

        if location_id is None:
            raise ValidationError(
                _('You need to provide a valid id for the location.'))

        location = Location.browse(location_id)

        if not location:
            raise ValidationError(_("Unknown location id '%d'." % location_id))

        return location.process_perpetual_inventory_request(request)
