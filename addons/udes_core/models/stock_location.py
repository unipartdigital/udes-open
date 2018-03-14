# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime

from odoo import fields, models,  _
from odoo.exceptions import ValidationError


PI_COUNT_MOVES = 'pi_count_moves'
INVENTORY_ADJUSTMENTS = 'inventory_adjustments'
PRECEDING_INVENTORY_ADJUSTMENTS = 'preceding_inventory_adjustments'


class StockLocation(models.Model):
    _name = 'stock.location'
    # Add messages to locations.
    _inherit = ['stock.location', 'mail.thread']

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility='onchange')

    u_date_last_checked = fields.Datetime(
        'Date Last Checked',
        help="The date that the location stock was last checked")

    u_date_last_checked_correct = fields.Datetime(
        'Date Last Checked correct',
        help="The date that the location stock was last checked and all "
             "products were correct")

    def _prepare_info(self, extended=False, load_quants=False):
        """
            Prepares the following info of the location in self:
            - id: int
            - name: string
            - barcode: string

            When load_quants is True also return:
            - quant_ids: [{stock.quants}]
        """
        self.ensure_one()

        info = {"id": self.id,
                "name": self.name,
                "barcode": self.barcode,
                }
        if load_quants:
            info['quants_ids'] = self.quant_ids.get_info()

        return info

    def get_info(self, **kwargs):
        """ Return a list with the information of each location in self.
        """
        res = []
        for loc in self:
            res.append(loc._prepare_info(**kwargs))

        return res

    def get_location(self, location_identifier):
        """ Get locations from a name, barcode, or id.
        """
        if isinstance(location_identifier, int):
            domain = [('id', '=', location_identifier)]
        elif isinstance(location_identifier, str):
            domain = ['|', ('barcode', '=', location_identifier),
                           ('name', '=', location_identifier)]
        else:
            raise ValidationError(
                _('Unable to create domain for location search from '
                  'identifier of type %s') % type(location_identifier))

        results = self.search(domain)

        if not results:
            raise ValidationError(
                _('Location not found for identifier %s')
                % str(location_identifier))

        if len(results) > 1:
            raise ValidationError(
                _('Too many locations found for identifier %s')
                % str(location_identifier))

        return results

    def _check_locations(self, loc_keys, obj):
        Location = self.env['stock.location']

        for key in loc_keys:
            loc_id = obj[key]

            if not Location.browse(loc_id).exists():
                raise ValidationError(
                    _("The request has an unknown location, id: '%d'.") % loc_id)

    def _validate_perpetual_inventory_request(self, request):
        if PI_COUNT_MOVES in request:
            for obj in request[PI_COUNT_MOVES]:
                self._check_locations(['location_id', 'location_dest_id'], obj)

        if PRECEDING_INVENTORY_ADJUSTMENTS in request:
            if not request.get(INVENTORY_ADJUSTMENTS):
                raise ValidationError(
                    _('You must specify inventory adjustments if you require '
                      'preceding adjustments.'))

            self._check_request_locations(['location_id'],
                                          request[INVENTORY_ADJUSTMENTS])

    def process_perpetual_inventory(self, request):
        """
            Executes the specified PI request by processing PI count
            moves, inventory adjustments, and preceding inventory
            adjustments. Updates the PI date time attributes (last
            check dates) accordingly.

            Raises a ValidationError in case of invalid request (e.g.
            one of the specified locations doesn't exist).

            Returns True in case any change as been made, False
            otherwise.
        """
        self._validate_perpetual_inventory_request(request)
        pi_outcome = defaultdict()

        if PI_COUNT_MOVES in request:
            pi_outcome[PI_COUNT_MOVES] = \
                self._process_pi_count_moves(request[PI_COUNT_MOVES])

        if INVENTORY_ADJUSTMENTS in request:
            adjs = request[INVENTORY_ADJUSTMENTS]
            adj_inv = self._process_inventory_adjustments(adjs)

            for pre_adj in request.get(PRECEDING_INVENTORY_ADJUSTMENTS, []):
                self._process_preceding_inventory_adjustments(pre_adj, adj_inv)

            pi_outcome[INVENTORY_ADJUSTMENTS] = adj_inv

        self._process_pi_datetime(pi_outcome)

        # @todo: reponse format?
        return bool(pi_outcome)

    def _process_pi_count_moves(self, moves_request):
        """
            Returns the modified inventory in case changes were
            necessary, None otherwise.
        """
        # @todo
        pass

    def _process_inventory_adjustments(self, adjustments_request):
        """
            Returns the modified inventory in case changes were
            necessary, None otherwise.
        """
        # @todo
        pass

    def _process_preceding_inventory_adjustments(self, pre_adj, next_adj_inv):
        Location = self.env['stock.location']

        # @todo: do we need casting here?
        location_id = int(pre_adj['location_id'])
        location = Location.browse(location_id)
        other_adjs = pre_adj[INVENTORY_ADJUSTMENTS]
        inv = location._process_inventory_adjustment(other_adjs)
        inv.u_next_inventory_id = next_adj_inv

    def _process_pi_datetime(self, pi_outcome):
        current_time = datetime.now()
        self.write({'u_date_last_checked': current_time})

        if all([pi_outcome[key] is None
                for key in [PI_COUNT_MOVES, INVENTORY_ADJUSTMENTS]]):
            # No PI changes - the location is in a correct state
            self.write({'u_date_last_checked_correct': current_time})
