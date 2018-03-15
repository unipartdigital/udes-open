# -*- coding: utf-8 -*-

from collections import defaultdict, namedtuple
from datetime import datetime

from odoo import fields, models,  _
from odoo.exceptions import ValidationError


PI_COUNT_MOVES = 'pi_count_moves'
INVENTORY_ADJUSTMENTS = 'inventory_adjustments'
PRECEDING_INVENTORY_ADJUSTMENTS = 'preceding_inventory_adjustments'

NO_PACKAGE_TOKEN = 'NO_PACKAGE'
NEW_PACKAGE_TOKEN = 'NEWPACKAGE'


StockInfoPI = namedtuple('StockInfoPI', ['product_id', 'package_id', 'lot_id'])


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

    def process_perpetual_inventory_request(self, request):
        """
            Executes the specified PI request by processing PI count
            moves, inventory adjustments, and preceding inventory
            adjustments. Updates the PI date time attributes (last
            check dates) accordingly.

            Expects a singleton.
            Expects a `request` argument that complies with the PI
            endpoint request schema.

            Raises a ValidationError in case of invalid request (e.g.
            one of the specified locations, packages, or products
            doesn't exist).

            Returns True.
        """
        self.ensure_one()
        self._validate_perpetual_inventory_request(request)
        pi_outcome = defaultdict()

        if PI_COUNT_MOVES in request:
            pi_outcome[PI_COUNT_MOVES] = \
                self._process_pi_count_moves(request[PI_COUNT_MOVES])

        if INVENTORY_ADJUSTMENTS in request:
            adjusted_inv = \
                self._process_inventory_adjustments(request[INVENTORY_ADJUSTMENTS])

            for pre_adjs_req in request.get(PRECEDING_INVENTORY_ADJUSTMENTS, []):
                self._process_single_preceding_adjustments_request(pre_adjs_req,
                                                                   adjusted_inv)

            pi_outcome[INVENTORY_ADJUSTMENTS] = adjusted_inv

        self._process_pi_datetime(pi_outcome)

        return True

    def _process_single_preceding_adjustments_request(self,
                                                      pre_adjs_request,
                                                      next_adjusted_inv):
        """
            Process the inventory adjustments for the location
            specified in the request.
            Assings the next inventory field of the new inventory
            to the specified next adjusted inventory instance.

            Raises a ValidationError in case the location does not
            exist.
        """
        Location = self.env['stock.location']

        location = Location.get_location(int(pre_adjs_request['location_id']))
        inv = location._process_inventory_adjustments(
            pre_adjs_request[INVENTORY_ADJUSTMENTS])
        inv.u_next_inventory_id = next_adjusted_inv

    def _process_pi_datetime(self, pi_outcome):
        current_time = datetime.now()
        self.write({'u_date_last_checked': current_time})

        if all([pi_outcome.get(key) is None
                for key in [PI_COUNT_MOVES, INVENTORY_ADJUSTMENTS]]):
            # No PI changes - the location is in a correct state
            self.write({'u_date_last_checked_correct': current_time})

    def _process_pi_count_moves(self, count_moves_request):
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
        Inventory = self.env['stock.inventory']
        InventoryLine = self.env['stock.inventory.line']

        stock_drift = self._get_stock_drift(adjustments_request)

        if not stock_drift:
            return

        inventory_adjustment = Inventory.create({
            'name':        'PI inventory adjustment ' + self.name,
            'location_id': self.id,
            'filter':      'none',
            'state':       'confirm'
        })

        for stock_info, quantity in stock_drift.items():
            InventoryLine.create({
              'inventory_id': inventory_adjustment.id,
              'product_id':   stock_info.product_id,
              'product_qty':  quantity,
              'location_id':  self.id,
              'package_id':   stock_info.package_id,
              'prod_lot_id':  stock_info.lot_id})

        return inventory_adjustment

    def _get_stock_drift(self, adjustments_request):
        """
            Returns a dictionary where keys are StockInfoPI instances
            and values are integers representing a product quantity.
            Each StockInfo is the result of the processing of an
            adjustments_request entry.

            Creates a lot for a given product if necessary, when the
            related lot name doesn't exist.

            Raises a ValidationError in case any specified product
            or package doesn't exist.
        """
        Product = self.env['product.product']
        Package = self.env['stock.quant.package']
        Lot = self.env['stock.production.lot']

        stock_drift = {}
        new_packages = {}

        for adj in adjustments_request:
            product = Product.get_product(int(adj['product_id']))

            # determine the package

            package_name = adj['package_name']
            package = None

            if NO_PACKAGE_TOKEN in package_name:
                pass
            elif NEW_PACKAGE_TOKEN in package_name:
                if package_name in new_packages:
                    package = new_packages[package_name]
                else:
                    package = Package.create({})
                    new_packages[package_name] = package
            else:
                package = Package.get_package(package_name)

            package_id = False if package is None else package.id

            # determine the lot

            lot_id = False

            if product.tracking != 'none' and 'lot_name' in adj:
                lot = Lot.get_lot(adj['lot_name'], product.id, create=True)
                lot_id = lot.id

            # add the entry

            info = StockInfoPI(product.id, package_id, lot_id)
            stock_drift[info] = adj['quantity']

        return stock_drift
