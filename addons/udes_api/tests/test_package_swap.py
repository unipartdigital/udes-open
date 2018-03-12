# -*- coding: utf-8 -*-

from odoo.addons.udes_core.tests import common
from odoo.exceptions import ValidationError


EXPECTED_PACKAGE_NAME = 'test_expected_package'
SCANNED_PACKAGE_NAME = 'test_scanned_package'


class TestPackageSwap(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestPackageSwap, cls).setUpClass()
        User = cls.env['res.users']

        user_warehouse = User.get_user_warehouse()
        cls.picking_type_pick = user_warehouse.pick_type_id
        cls.pack_4apples_info = [{'product': cls.apple,
                                  'qty': 4}]

    def setUp(self):
        super(TestPackageSwap, self).setUp()
        Package = self.env['stock.quant.package']

        self.picking_type_pick.u_reserve_as_packages = True
        self.picking_type_pick.u_allow_swapping_packages = True
        self.expected_package = Package.get_package(EXPECTED_PACKAGE_NAME,
                                                    create=True)
        self.scanned_package = Package.get_package(SCANNED_PACKAGE_NAME,
                                                   create=True)

    def test01_error_if_not_allowed_to_swap(self):
        """ Should error if the 'allow swap' attr is unflagged """
        self.picking_type_pick.u_allow_swapping_packages = False
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)

        with self.assertRaises(ValidationError):
            picking.update_picking(package_name=SCANNED_PACKAGE_NAME,
                                   expected_package_name=EXPECTED_PACKAGE_NAME)

    def test02_reserved_and_unreserved(self):
        """
        Should error when swapping two packages:
         - with same contents;
         - in the same location;
         - the scanned package is reserved, the expected one not.

        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.expected_package.id)

        # checking pre-conditions
        self.assertTrue(self.scanned_package.is_reserved())
        self.assertFalse(self.expected_package.is_reserved())

        with self.assertRaises(ValidationError) as err:
            picking.update_picking(package_name=SCANNED_PACKAGE_NAME,
                                   expected_package_name=EXPECTED_PACKAGE_NAME)

        self.assertEqual(
            err.exception.name,
            "Expected package cannot be found in picking %s" % picking.name)

    def test03_unreserved_and_reserved(self):
        """
        Should successfully swap two packages:
         - with same contents;
         - in the same location;
         - the scanned package is not reserved, the expected one is.

        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.expected_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)

        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.scanned_package.id)

        # checking pre-conditions
        self.assertFalse(self.scanned_package.is_reserved())
        self.assertTrue(self.expected_package.is_reserved())

        # method under test
        picking.update_picking(package_name=SCANNED_PACKAGE_NAME,
                               expected_package_name=EXPECTED_PACKAGE_NAME)

        # checking outcome

        e_pack_quants = self.expected_package._get_contained_quants()[0]
        s_pack_quants = self.scanned_package._get_contained_quants()[0]

        self.assertFalse(self.expected_package.is_reserved(),
                         "Expected package is not unreserved after swap")
        self.assertEqual(int(e_pack_quants.reserved_quantity), 0,
                         "Got reserved quantities for the expected package")
        self.assertTrue(self.scanned_package.is_reserved(),
                        "Scanned package is not reserved after swap")
        self.assertEqual(int(s_pack_quants.reserved_quantity), 4,
                         "Wrong reserved quants for the scanned package")

        expected_mls = picking.move_line_ids.filtered(
            lambda ml: ml.package_id == self.expected_package)
        scanned_mls = picking.move_line_ids.filtered(
            lambda ml: ml.package_id == self.scanned_package)

        self.assertEqual(len(expected_mls), 0,
                         "Got move lines related to the expected package")
        self.assertEqual(len(scanned_mls), 1,
                         "Don't have unique move line for the scanned package")
        self.assertEqual(scanned_mls[0].package_id, self.scanned_package,
                         "Move lines don't point to scanned package")
        self.assertEqual(scanned_mls[0].result_package_id,
                         self.scanned_package,
                         "Move lines don't point to scanned package as result")

    def test04_both_reserved(self):
        """
        Should successfully swap two packages:
         - with same contents;
         - in the same location;
         - both scanned and expected packages are reserved.

        In this case, the expected package shouldn't change
        its state after update_picking is invoked.
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.expected_package.id)
        picking01 = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True)

        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.scanned_package.id)
        picking02 = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True)

        # checking pre-conditions
        self.assertTrue(self.scanned_package.is_reserved())
        self.assertTrue(self.expected_package.is_reserved())

        # method under test
        picking01.update_picking(
            package_name=SCANNED_PACKAGE_NAME,
            expected_package_name=EXPECTED_PACKAGE_NAME)

        # checking outcome

        s_pack_quants = self.scanned_package._get_contained_quants()[0]

        self.assertTrue(self.expected_package.is_reserved(),
                        "Expected package is not reserved after swap")
        self.assertTrue(self.scanned_package.is_reserved(),
                        "Scanned package is not reserved after swap")
        self.assertEqual(int(s_pack_quants.reserved_quantity), 4,
                         "Wrong reserved quants for the scanned package")

        scanned_mls = self.scanned_package.find_move_lines()

        self.assertEqual(len(scanned_mls), 1,
                         "Don't have unique move line for the scanned package")
        self.assertEqual(scanned_mls[0].picking_id.id, picking01.id,
                         "Move lines don't point to expected picking")
        self.assertEqual(scanned_mls[0].package_id, self.scanned_package,
                         "Move lines don't point to scanned package")
        self.assertEqual(scanned_mls[0].result_package_id, self.scanned_package,
                         "Move lines don't point to scanned package as result")

    def test05_error_if_different_locations(self):
        """ Should fail if packages are in different locations. """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id, self.test_location_02.id, 4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)

        with self.assertRaises(ValidationError):
            picking.update_picking(package_name=SCANNED_PACKAGE_NAME,
                                   expected_package_name=EXPECTED_PACKAGE_NAME)

    def test06_error_if_different_package_product(self):
        """ Should error if package products are different """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.expected_package.id)
        self.create_quant(self.banana.id, self.test_location_01.id, 4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)

        with self.assertRaises(ValidationError):
            picking.update_picking(package_name=SCANNED_PACKAGE_NAME,
                                   expected_package_name=EXPECTED_PACKAGE_NAME)

    def test07_error_if_different_package_qty(self):
        """ Should error if products' qty are different """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id, self.test_location_01.id, 8,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)

        with self.assertRaises(ValidationError):
            picking.update_picking(package_name=SCANNED_PACKAGE_NAME,
                                   expected_package_name=EXPECTED_PACKAGE_NAME)

    def test08_error_if_different_picking_type(self):
        """
        Should error when swapping two packages:
         - with same contents;
         - in the same location;
         - both scanned and expected packages are reserved, but
           with different picking types.

        """
        PickingType = self.env['stock.picking.type']

        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        
        self.picking_type_internal.u_reserve_as_packages = True
        self.picking_type_internal.u_allow_swapping_packages = True
        self.create_picking(self.picking_type_internal,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)

        # checking pre-conditions
        self.assertTrue(self.scanned_package.is_reserved())
        self.assertTrue(self.expected_package.is_reserved())

        with self.assertRaises(ValidationError):
            picking.update_picking(package_name=SCANNED_PACKAGE_NAME,
                                   expected_package_name=EXPECTED_PACKAGE_NAME)
