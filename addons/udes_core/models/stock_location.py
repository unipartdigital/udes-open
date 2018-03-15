# -*- coding: utf-8 -*-

from collections import namedtuple
from datetime import datetime

from odoo import fields, models,  _
from odoo.exceptions import ValidationError


PI_COUNT_MOVES = 'pi_count_moves'
INVENTORY_ADJUSTMENTS = 'inventory_adjustments'
PRECEDING_INVENTORY_ADJUSTMENTS = 'preceding_inventory_adjustments'

NO_PACKAGE_TOKEN = 'NO_PACKAGE'
NEW_PACKAGE_TOKEN = 'NEWPACKAGE'


StockInfoPI = namedtuple('StockInfoPI', ['product_id', 'package_id', 'lot_id'])


class PIOutcome:
    def __init__(self):
        self.moves_inventory = None
        self.adjustment_inventory = None

    def got_inventory_changes(self):
        return self.moves_inventory is not None \
            or self.adjustment_inventory is not None

#
## StockLocation
#


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

        # @todo: (ale) consider renaming the entry to `quant_ids`
        # for consistency
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

    #
    ## Perpetual Inventory
    #

    def _check_obj_locations(self, loc_keys, obj):
        Location = self.env['stock.location']

        for key in loc_keys:
            loc_id = int(obj[key])

            if not Location.browse(loc_id).exists():
                raise ValidationError(_("The request has an unknown location, "
                                        "id: '%d'.") % loc_id)

    def _validate_perpetual_inventory_request(self, request):
        keys = ['location_id', 'location_dest_id']

        if PI_COUNT_MOVES in request:
            for obj in request[PI_COUNT_MOVES]:
                self._check_obj_locations(keys, obj)

        if PRECEDING_INVENTORY_ADJUSTMENTS in request:
            if not request.get(INVENTORY_ADJUSTMENTS):
                raise ValidationError(
                    _('You must specify inventory adjustments if you require '
                      'preceding adjustments.'))

            self._check_obj_locations(keys[:1], request[INVENTORY_ADJUSTMENTS])

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
        pi_outcome = PIOutcome()

        if PI_COUNT_MOVES in request:
            pi_outcome.moves_inventory = \
                self._process_pi_count_moves(request[PI_COUNT_MOVES])

        if INVENTORY_ADJUSTMENTS in request:
            pi_outcome.adjustment_inventory = \
                self._process_inventory_adjustments(request[INVENTORY_ADJUSTMENTS])

            for pre_adjs_req in request.get(PRECEDING_INVENTORY_ADJUSTMENTS, []):
                self._process_single_preceding_adjustments_request(
                    pre_adjs_req,
                    pi_outcome.adjustment_inventory)

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

        if not pi_outcome.got_inventory_changes():
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
