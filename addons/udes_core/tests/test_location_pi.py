# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import time

from . import common

from odoo.exceptions import ValidationError


ODOO_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class MockPIOutcome:
    def __init__(self, got_changes):
        self._got_changes = got_changes

    def got_inventory_changes(self):
        return self._got_changes


class TestLocationPI(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestLocationPI, cls).setUpClass()
        Location = cls.env['stock.location']
        User = cls.env['res.users']

        user_warehouse = User.get_user_warehouse()
        cls.picking_type_pick = user_warehouse.pick_type_id
        cls.datetime_tolerance = timedelta(minutes=1)

        loc_id = 9834247

        while Location.browse(loc_id).exists():
            if loc_id > 9835147:
                # done 100 attempts, that's enough
                cls.fail("Failed to determine an unknown location; "
                         "please use an empty database for testing")
            else:
                loc_id += 9

        cls.unknown_location_id = loc_id

    def setUp(self):
        super(TestLocationPI, self).setUp()
        Package = self.env['stock.quant.package']

        self.package_one = Package.get_package("test_pi_package_one",
                                               create=True)
        self.package_two = Package.get_package("test_pi_package_two",
                                               create=True)

    def test01_validate_pi_request_success_count_move(self):
        """ No error is raised if the PI count request request is valid """
        req = {
            'location_id': self.test_location_01.id,
            'pi_count_moves': [
                {
                    'quant_ids': [1, 2, 3],
                    'location_id': self.test_location_01.id,
                    'location_dest_id': self.test_location_02.id
                }
            ]
        }

        self.test_location_01._validate_perpetual_inventory_request(req)
        self.assertTrue(True)

    def test02_validate_pi_request_success_inventory_adjustment(self):
        """
        No error is raised if the PI inventory adjustment request
        is valid
        """
        req = {
            'location_id': self.test_location_01.id,
            'inventory_adjustments': [
                {
                    'product_id': self.apple.id,
                    'package_name': self.package_one.name,
                    'quantity': 4
                }
            ],
            'preceding_inventory_adjustments': {
                'location_id': self.test_location_01.id,
                'inventory_adjustments': [
                    {
                        'product_id': self.banana.id,
                        'package_name': self.package_two,
                        'quantity': 0
                    }
                ]
            }
        }

        self.test_location_01._validate_perpetual_inventory_request(req)
        self.assertTrue(True)

    def test03_validate_pi_request_failure_unknown_move_location(self):
        """ Errors if the request contains unknown move locations """
        req = {
            'location_id': self.test_location_01.id,
            'pi_count_moves': [
                {
                    'quant_ids': [1, 2, 3],
                    'location_id': self.test_location_01.id,
                    'location_dest_id': self.unknown_location_id
                }
            ]
        }

        with self.assertRaisesRegex(ValidationError,
                                    'The request has an unknown location'):
            self.test_location_01._validate_perpetual_inventory_request(req)

    def test04_validate_pi_request_failure_no_adj(self):
        """
        Errors if the request contains preceding adjustments but
        not inventory adjustments
        """
        req = {
            'location_id': self.test_location_01.id,
            'pi_count_moves': [
                {
                    'quant_ids': [1, 2, 3],
                    'location_id': self.test_location_01.id,
                    'location_dest_id': self.test_location_02.id
                }
            ],
            'preceding_inventory_adjustments': {
                'location_id': self.test_location_01.id,
                'inventory_adjustments': [
                    {'product_id': 7, 'package_name': 'foo', 'quantity': 0}
                ]
            }
        }

        with self.assertRaisesRegex(ValidationError,
                                    'You must specify inventory adjustments'):
            self.test_location_01._validate_perpetual_inventory_request(req)

    def test05_validate_pi_request_failure_unknown_adjustment_location(self):
        """ Errors if the request contains unknown locations """
        req = {
            'location_id': self.test_location_01.id,
            'inventory_adjustments': [
                {
                    'product_id': self.apple.id,
                    'package_name': self.package_one.name,
                    'quantity': 4
                }
            ],
            'preceding_inventory_adjustments': {
                'location_id': self.unknown_location_id,
                'inventory_adjustments': [
                    {
                        'product_id': self.banana.id,
                        'package_name': self.package_two,
                        'quantity': 0
                    }
                ]
            }
        }

        with self.assertRaisesRegex(ValidationError,
                                    'The request has an unknown location'):
            self.test_location_01._validate_perpetual_inventory_request(req)

    def test06_validate_pi_request_failure_lot_with_untracked_product(self):
        """
        Errors if the request contains an inventory adjustment entry
        for an untracked product with a lot name specified
        """
        req = {
            'location_id': self.test_location_01.id,
            'inventory_adjustments': [
                {
                    'product_id': self.apple.id,
                    'package_name': self.package_one.name,
                    'quantity': 1,
                    'lot_name': 'awesome_lot'
                }
            ]
        }

        with self.assertRaisesRegex(
                ValidationError, "Product '%s' is not tracked, but a lot name "
                                 "has been specified." % self.apple.name):
            self.test_location_01._validate_perpetual_inventory_request(req)

    def test07_validate_pi_request_failure_tracked_product_without_lot(self):
        """
        Errors if the request contains an inventory adjustment entry
        for a tracked product without a lot name
        """
        req = {
            'location_id': self.test_location_01.id,
            'inventory_adjustments': [
                {
                    'product_id': self.strawberry.id,
                    'package_name': self.package_one.name,
                    'quantity': 1
                }
            ]
        }

        with self.assertRaisesRegex(
                ValidationError, "Product '%s' is tracked, but the lot name "
                                 "is not specified." % self.strawberry.name):
            self.test_location_01._validate_perpetual_inventory_request(req)

    def test08_validate_pi_request_failure_tracked_product_invalid_qty(self):
        """
        Errors if the request contains an inventory adjustment entry
        for a tracked product with an invalid quantity value
        """
        req = {
            'location_id': self.test_location_01.id,
            'inventory_adjustments': [
                {
                    'product_id': self.strawberry.id,
                    'package_name': self.package_one.name,
                    'quantity': 4,
                    'lot_name': 'beautiful_lot'
                }
            ]
        }

        with self.assertRaisesRegex(
                ValidationError, "Product '%s' is tracked, but the quantity "
                                 "is 4." % self.strawberry.name):
            self.test_location_01._validate_perpetual_inventory_request(req)

    def test09_process_pi_datetime_no_changes(self):
        """
        Both last check & last correct PI datetime are updated if
        the PIOutcome is empty
        """
        outcome = MockPIOutcome(False)
        old_dt_checked = self.test_location_01.u_date_last_checked
        old_dt_success = self.test_location_01.u_date_last_checked_correct
        time.sleep(1)

        self.test_location_01._process_pi_datetime(outcome)

        self.assertNotEqual(old_dt_checked,
                            self.test_location_01.u_date_last_checked,
                            "The checked datetime was not updated.")

        self.assertNotEqual(old_dt_success,
                            self.test_location_01.u_date_last_checked_correct,
                            "The last correct datetime was not updated.")

    def test10_process_pi_datetime_with_inventory_changes(self):
        """
        Only the last check datetime is updated if the PIOutcome
        is not empty
        """
        outcome = MockPIOutcome(True)
        old_dt_checked = self.test_location_01.u_date_last_checked
        old_dt_success = self.test_location_01.u_date_last_checked_correct
        time.sleep(1)

        self.test_location_01._process_pi_datetime(outcome)

        self.assertNotEqual(old_dt_checked,
                            self.test_location_01.u_date_last_checked,
                            "The checked datetime was not updated.")

        self.assertEqual(old_dt_success,
                         self.test_location_01.u_date_last_checked_correct,
                         "The last correct datetime was wrongly updated.")

    #
    ## PI count moves
    #

    def _check_picking_loc01_to_loc02(self, picking, picking_idx,
                                      check_single_move_line=True):
        self.assertEqual(picking.location_id.id, self.test_location_01.id,
                         "Picking %d has wrong source location" % picking_idx)
        self.assertEqual(picking.location_dest_id.id, self.test_location_02.id,
                         "Picking %d has wrong dest location" % picking_idx)
        self.assertTrue(picking.has_packages,
                        "Picking %d does not have packages" % picking_idx)

        if check_single_move_line:
            self.assertEqual(len(picking.move_line_ids), 1,
                            "Picking %d has not single move line" % picking_idx)

    def test11_process_pi_count_moves_valid_request_with_package(self):
        """ Successfully creates the expected picking """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        count_moves = [{"package_id": self.package_one.id,
                        "location_id": self.test_location_01,
                        "location_dest_id": self.test_location_02.id}]

        pickings = self.test_location_02._process_pi_count_moves(count_moves)

        self.assertEqual(len(pickings), 1,
                         "Did not create exactly one picking")
        self._check_picking_loc01_to_loc02(pickings[0], 0)
        self.assertEqual(pickings[0].move_line_ids[0].package_id.id,
                         self.package_one.id,
                         "Picking is not related to the specified package")

    def test12_process_pi_count_moves_valid_request_with_2_packages(self):
        """
        Successfully creates the two expected pickings when two
        count moves items are specified, both with packages.
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        self.create_quant(self.banana.id, self.test_location_01.id, 13,
                          package_id=self.package_two.id)
        count_moves = [
            {
                "package_id": self.package_one.id,
                "location_id": self.test_location_01,
                "location_dest_id": self.test_location_02.id
            },
            {
                "package_id": self.package_two.id,
                "location_id": self.test_location_01,
                "location_dest_id": self.test_location_02.id
            }
        ]

        pickings = self.test_location_01._process_pi_count_moves(count_moves)

        self.assertEqual(len(pickings), 2,
                         "Did not create exactly two picking")

        for idx in range(2):
            self._check_picking_loc01_to_loc02(pickings[idx], idx)

        self.assertEqual(pickings[0].move_line_ids[0].package_id.id,
                         self.package_one.id,
                         "Picking 0 is not related to the specified package")
        self.assertEqual(pickings[1].move_line_ids[0].package_id.id,
                         self.package_two.id,
                         "Picking 1 is not related to the specified package")

    def test13_process_pi_count_moves_valid_request_with_quant(self):
        """
        Successfully creates the expected picking when a quant is
        specified.
        """
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 4,
                                  package_id=self.package_one.id)
        count_moves = [{"quant_ids": [quant.id],
                        "location_id": self.test_location_01,
                        "location_dest_id": self.test_location_02.id}]

        pickings = self.test_location_01._process_pi_count_moves(count_moves)

        self.assertEqual(len(pickings), 1,
                         "Did not create exactly one picking")
        self._check_picking_loc01_to_loc02(pickings[0], 0)
        self.assertEqual(pickings[0].move_line_ids[0].package_id.id,
                         self.package_one.id,
                         "Picking is not related to the specified package")

    def test14_process_pi_count_moves_valid_request_with_two_quants(self):
        """
        Successfully creates the expected picking when two quants are
        specified (two quants for different products, same package);
        expecting a picking with 2 move lines.
        """
        quant01 = self.create_quant(self.apple.id, self.test_location_01.id,
                                    13, package_id=self.package_one.id)
        quant02 = self.create_quant(self.banana.id, self.test_location_01.id,
                                    11, package_id=self.package_one.id)
        count_moves = [{"quant_ids": [quant01.id, quant02.id],
                        "location_id": self.test_location_01,
                        "location_dest_id": self.test_location_02.id}]

        pickings = self.test_location_01._process_pi_count_moves(count_moves)

        self.assertEqual(len(pickings), 1,
                         "Did not create exactly one picking")

        self._check_picking_loc01_to_loc02(pickings[0], 0,
                                           check_single_move_line=False)
        self.assertEqual(len(pickings[0].move_line_ids), 2,
                         "Did not create a picking with 2 move lines")

        for move_line in pickings[0].move_line_ids:
            self.assertEqual(move_line.package_id.id, self.package_one.id,
                             "Picking is not related to the specified package")

    def test15_process_pi_count_moves_bad_request_with_reserved_package(self):
        """
        Throws a ValidationError in case the specified package is
        reserved. Checking by specifying both package / quants list.
        """
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 4,
                                  package_id=self.package_one.id)
        self.create_picking(self.picking_type_pick,
                            products_info=[{'product': self.apple,
                                            'qty': 4}],
                            confirm=True,
                            assign=True)
        requests = [
            [{
                "package_id": self.package_one.id,
                "location_id": self.test_location_01,
                "location_dest_id": self.test_location_02.id
            }],
            [{
                "quant_ids": [quant.id],
                "location_id": self.test_location_01,
                "location_dest_id": self.test_location_02.id
            }]
        ]

        for count_moves in requests:
            with self.assertRaisesRegex(ValidationError,
                                        "Some quants are already reserved"):
                self.test_location_01._process_pi_count_moves(count_moves)

    #
    ## PI Inventory Adjustments
    #

    def test16_process_inventory_adjustments_returns_None_when_no_drift(self):
        """ Returns None when no request item is specified """
        inv = self.test_location_01._process_inventory_adjustments([])

        self.assertIsNone(inv, "Returned a new inventory for empty request")

    def test17_get_stock_drift_no_package_token(self):
        """
        Returns the correct metadata for the picking creation if
        a request item contains a 'NO_PACKAGE' package.
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4)
        adjs_req = [{"product_id": self.apple.id,
                     "package_name": "test14_NO_PACKAGE",
                     "quantity": 8}]

        stock_drift = self.test_location_01._get_stock_drift(adjs_req)

        self.assertEqual(len(stock_drift), 1, "Not a unique stock drift entry")

        (stock_info, qty), = stock_drift.items()

        self.assertEqual(qty, 8, "Wrong adjustment quantity")
        self.assertEqual(stock_info.product_id, self.apple.id,
                         "Wrong product id")
        self.assertFalse(stock_info.package_id, "Wrongly added a product id")
        self.assertFalse(stock_info.lot_id, "Wrongly added a lot id")

    def test18_get_stock_drift_new_package_token(self):
        """
        Returns the correct metadata for the picking creation if
        a request item contains a 'NEWPACKAGE' package.
        """
        Package = self.env['stock.quant.package']

        test_start_date = datetime.now() - self.datetime_tolerance
        new_package_name = "test15_NEWPACKAGE"
        self.create_quant(self.apple.id, self.test_location_01.id, 4)
        adjs_req = [{"product_id": self.apple.id,
                     "package_name": new_package_name,
                     "quantity": 6}]

        stock_drift = self.test_location_01._get_stock_drift(adjs_req)

        self.assertEqual(len(stock_drift), 1, "Not a unique stock drift entry")

        (stock_info, qty), = stock_drift.items()

        self.assertEqual(qty, 6, "Wrong adjustment quantity")
        self.assertEqual(stock_info.product_id, self.apple.id,
                         "Wrong product id")
        self.assertIsNotNone(stock_info.package_id,
                             "Does not contain a package")

        new_package = Package.get_package(stock_info.package_id)
        new_package_date = datetime.strptime(new_package.create_date,
                                             ODOO_DATETIME_FORMAT)

        self.assertTrue(new_package_date >= test_start_date,
                        "New package does not seem new")
        self.assertFalse(stock_info.lot_id, "Wrongly added a lot id")

    def test19_get_stock_drift_new_package_token_multiple_products(self):
        """
        Returns the correct metadata for the picking creation if
        a request item contains a 'NEWPACKAGE' package; multiple
        product requests, with the same package name.
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_location_01.id, 6)
        adjs_req = [{"product_id": self.apple.id,
                     "package_name": "test16_NEWPACKAGE",
                     "quantity": 15},
                    {"product_id": self.banana.id,
                     "package_name": "test16_NEWPACKAGE",
                     "quantity": 16}]

        stock_drift = self.test_location_01._get_stock_drift(adjs_req)

        self.assertEqual(len(stock_drift), 2,
                         "Does not contain two stock drift entries")

        package_ids = []

        for stock_info, qty in stock_drift.items():
            if stock_info.product_id == self.apple.id:
                self.assertEqual(qty, 15, "Wrong quantity")
            elif stock_info.product_id == self.banana.id:
                self.assertEqual(qty, 16, "Wrong quantity")
            else:
                self.fail("Unexpected product id")

            package_ids.append(stock_info.package_id)

        self.assertEqual(package_ids[0], package_ids[1],
                         "Did not use the same package")

    def test20_get_stock_drift_two_new_package_token_multiple_products(self):
        """
        Returns the correct metadata for the picking creation if
        a request item contains two 'NEWPACKAGE' packages; multiple
        product requests, with the different package names (multiple
        packages will be created).
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_location_01.id, 6)
        adjs_req = [{"product_id": self.apple.id,
                     "package_name": "test17_NEWPACKAGE_one",
                     "quantity": 25},
                    {"product_id": self.banana.id,
                     "package_name": "test17_NEWPACKAGE_two",
                     "quantity": 26}]

        stock_drift = self.test_location_01._get_stock_drift(adjs_req)

        self.assertEqual(len(stock_drift), 2,
                         "Does not contain two stock drift entries")

        package_ids = []

        for stock_info, qty in stock_drift.items():
            if stock_info.product_id == self.apple.id:
                self.assertEqual(qty, 25, "Wrong quantity")
            elif stock_info.product_id == self.banana.id:
                self.assertEqual(qty, 26, "Wrong quantity")
            else:
                self.fail("Unexpected product id")

            package_ids.append(stock_info.package_id)

        self.assertNotEqual(package_ids[0], package_ids[1],
                            "Did use the same package")

    def test21_get_stock_drift_new_package_token_more_products_one_adj(self):
        """
        Returns the correct metadata for the picking creation if
        a request item contains a single existent package; multiple
        products are within such package, but only one product needs
        to be adjusted.
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 65,
                          package_id=self.package_one.id)
        self.create_quant(self.banana.id, self.test_location_01.id, 66,
                          package_id=self.package_one.id)
        adjs_req = [{"product_id": self.apple.id,
                     "package_name": self.package_one.name,
                     "quantity": 34}]

        stock_drift = self.test_location_01._get_stock_drift(adjs_req)

        self.assertEqual(len(stock_drift), 1,
                         "Does not contain a single stock drift entries")

        (stock_info, qty), = stock_drift.items()

        self.assertEqual(stock_info.product_id, self.apple.id,
                         "Wrong product in the stock drift dictionary")
        self.assertEqual(qty, 34, "Wrong quantity")

    def test22_get_stock_drift_no_package_token_with_new_lot(self):
        """
        Returns the correct metadata for the picking creation if
        a request item contains a 'NO_PACKAGE' package and a lot
        is specified - the lot should be created if the product
        is tracked.
        """
        Lot = self.env['stock.production.lot']

        # NB: our strawberries are `tracking == 'serial'`
        lot_name = "test_19_lot"
        adjs_req = [{"product_id": self.strawberry.id,
                     "package_name": "tes19_NO_PACKAGE_with_new_lot",
                     "quantity": 1,
                     "lot_name": lot_name}]

        stock_drift = self.test_location_01._get_stock_drift(adjs_req)

        self.assertEqual(len(stock_drift), 1, "Not a unique stock drift entry")

        (stock_info, qty), = stock_drift.items()

        self.assertEqual(qty, 1, "Wrong adjustment quantity")
        self.assertEqual(stock_info.product_id, self.strawberry.id,
                         "Wrong product id")
        self.assertFalse(stock_info.package_id, "Wrongly added a product id")
        self.assertTrue(stock_info.lot_id is not False, "No lot specified")

        lot = Lot.browse(stock_info.lot_id)

        self.assertTrue(lot.exists(), "New lot does not exist")
        self.assertEqual(lot.name, lot_name, "New lot has an unexpected name")
        self.assertEqual(lot.product_id.id, self.strawberry.id,
                         "New lot is linked to an unexpected product")

    def test23_get_stock_drift_no_package_token_with_existent_lot(self):
        """
        Returns the correct metadata for the picking creation if
        a request item contains a 'NO_PACKAGE' package and an
        existent lot is specified.
        """
        Lot = self.env['stock.production.lot']

        # NB: a quant for a serial tracked item should have the
        # lot_id set and qty = 1
        lot_name = "test_20_lot"
        lot = Lot.get_lot(lot_name, self.strawberry.id, create=True)
        self.create_quant(self.strawberry.id, self.test_location_01.id, 1,
                          lot_id=lot.id)
        adjs_req = [{"product_id": self.strawberry.id,
                     "package_name": "test20_NO_PACKAGE_with_existent_lot",
                     "quantity": 0,
                     "lot_name": lot_name}]

        stock_drift = self.test_location_01._get_stock_drift(adjs_req)

        self.assertEqual(len(stock_drift), 1, "Not a unique stock drift entry")

        (stock_info, qty), = stock_drift.items()

        self.assertEqual(qty, 0, "Wrong adjustment quantity")
        self.assertEqual(stock_info.product_id, self.strawberry.id,
                         "Wrong product id")
        self.assertFalse(stock_info.package_id, "Wrongly added a product id")
        self.assertEqual(stock_info.lot_id, lot.id, "Wrong lot specified")

    def test24_process_inventory_adjustment_mss(self):
        """
        Returns the expected stock.inventory.line representing
        the requested inventory adjustment, after a valid request.
        """
        Inventory = self.env['stock.inventory']

        self.create_quant(self.apple.id, self.test_location_01.id, 4)
        adjs_req = [{"product_id": self.apple.id,
                     "package_name": "test21_NO_PACKAGE",
                     "quantity": 3}]
        expected_name = 'PI inventory adjustment ' + self.test_location_01.name

        inv_adj = self.test_location_01\
                      ._process_inventory_adjustments(adjs_req)

        self.assertEqual(inv_adj.name, expected_name,
                         "Unexpected inventory adjustment name")

        inv = Inventory.search([('name', '=', inv_adj.name)])

        self.assertEqual(len(inv), 1, "Did not create the inventory")

        inv_line = inv.line_ids

        self.assertEqual(len(inv_line), 1,
                         "Did not add a single inventory line")
        self.assertEqual(inv_line.product_qty, 3, "Wrong quantity")
        self.assertFalse(inv_line.package_id,
                         "A package has been wrongly associated")
        self.assertFalse(inv_line.prod_lot_id,
                         "A lot has been wrongly associated")
        self.assertEqual(inv_line.location_id.id, self.test_location_01.id,
                         "Inventory line associated to the wrong location")

    def test25_process_single_preceding_adjustments_request_mss(self):
        """
        Correctly processes the specified preceding adjustment
        request and links it to the specified inventory adjustment.
        """
        Inventory = self.env['stock.inventory']

        package_name = "test22_NO_PACKAGE_with_lot"
        adjs_req = [{"product_id": self.banana.id,
                     "package_name": package_name,
                     "quantity": 28}]
        inv_adj = self.test_location_01\
                      ._process_inventory_adjustments(adjs_req)

        # pre-conditions
        self.assertEqual(len(inv_adj), 1)
        self.assertEqual(len(inv_adj.u_preceding_inventory_ids), 0)

        inv_id = inv_adj.id
        prec_req = {
            "location_id": self.test_location_01.id,
            "inventory_adjustments": [{"product_id": self.apple.id,
                                       "package_name": package_name,
                                       "quantity": 3}]
        }

        self.test_location_01\
            ._process_single_preceding_adjustments_request(prec_req, inv_adj)

        self.assertEqual(len(inv_adj.u_preceding_inventory_ids), 1,
                         "The preceding adjustments were not linked")

        prec_inv_id = inv_adj.u_preceding_inventory_ids.id
        prec_inv = Inventory.browse(prec_inv_id)

        self.assertTrue(prec_inv.exists(),
                        "The preceding adjustments inventory doesn't exist")
        self.assertEquals(prec_inv.u_next_inventory_id.id, inv_id,
                          "The preceding adjustments inventory is not linked "
                          "correctly to the next inventory adjustments")
