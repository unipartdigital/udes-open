# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import ValidationError

EXPECTED_PACKAGE_NAME = 'test_expected_package'
SCANNED_PACKAGE_NAME = 'test_scanned_package'


class TestPackageSwap(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestPackageSwap, cls).setUpClass()
        cls.pack_4apples_info = [{'product': cls.apple, 'qty': 4}]
        cls.picking_type_internal.default_location_src_id = \
            cls.test_location_01.id

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
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        with self.assertRaises(ValidationError):
            picking.update_picking(
                package_name=SCANNED_PACKAGE_NAME,
                expected_package_names=[EXPECTED_PACKAGE_NAME])

    def test02_reserved_and_unreserved(self):
        """
        Should error when swapping two packages:
         - with same contents;
         - in the same location;
         - the scanned package is reserved, the expected one not.

        """
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)

        # checking pre-conditions
        self.assertTrue(self.scanned_package.is_reserved())
        self.assertFalse(self.expected_package.is_reserved())

        with self.assertRaises(ValidationError) as err:
            picking.update_picking(
                package_name=SCANNED_PACKAGE_NAME,
                expected_package_names=[EXPECTED_PACKAGE_NAME])

        self.assertEqual(
            err.exception.name,
            "Expected package(s) cannot be found in picking %s" % picking.name)

    def test03_unreserved_and_reserved(self):
        """
        Should successfully swap two packages:
         - with same contents;
         - in the same location;
         - the scanned package is not reserved, the expected one is.

        """
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.scanned_package.id)

        # checking pre-conditions
        self.assertFalse(self.scanned_package.is_reserved())
        self.assertTrue(self.expected_package.is_reserved())

        # method under test
        picking.update_picking(package_name=SCANNED_PACKAGE_NAME,
                               expected_package_names=[EXPECTED_PACKAGE_NAME])

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

        expected_mls = picking.move_line_ids.filtered(lambda ml: ml.package_id
                                                      == self.expected_package)
        scanned_mls = picking.move_line_ids.filtered(lambda ml: ml.package_id
                                                     == self.scanned_package)

        self.assertEqual(len(expected_mls), 0,
                         "Got move lines related to the expected package")
        self.assertEqual(
            len(scanned_mls), 1,
            "Don't have unique move line for the scanned package")
        self.assertEqual(scanned_mls[0].package_id, self.scanned_package,
                         "Move lines don't point to scanned package")
        self.assertEqual(
            scanned_mls[0].result_package_id, self.scanned_package,
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
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)
        picking01 = self.create_picking(self.picking_type_pick,
                                        products_info=self.pack_4apples_info,
                                        confirm=True,
                                        assign=True)
        picking01 = picking01.sudo(self.outbound_user)

        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.scanned_package.id)
        picking02 = self.create_picking(self.picking_type_pick,
                                        products_info=self.pack_4apples_info,
                                        confirm=True,
                                        assign=True)

        # checking pre-conditions
        self.assertTrue(self.scanned_package.is_reserved())
        self.assertTrue(self.expected_package.is_reserved())

        # method under test
        picking01.update_picking(
            package_name=SCANNED_PACKAGE_NAME,
            expected_package_names=[EXPECTED_PACKAGE_NAME])

        # checking outcome

        s_pack_quants = self.scanned_package._get_contained_quants()[0]

        self.assertTrue(self.expected_package.is_reserved(),
                        "Expected package is not reserved after swap")
        self.assertTrue(self.scanned_package.is_reserved(),
                        "Scanned package is not reserved after swap")
        self.assertEqual(int(s_pack_quants.reserved_quantity), 4,
                         "Wrong reserved quants for the scanned package")

        scanned_mls = self.scanned_package.find_move_lines()

        self.assertEqual(
            len(scanned_mls), 1,
            "Don't have unique move line for the scanned package")
        self.assertEqual(scanned_mls[0].picking_id.id, picking01.id,
                         "Move lines don't point to expected picking")
        self.assertEqual(scanned_mls[0].package_id, self.scanned_package,
                         "Move lines don't point to scanned package")
        self.assertEqual(
            scanned_mls[0].result_package_id, self.scanned_package,
            "Move lines don't point to scanned package as result")

    def test05_error_if_different_locations(self):
        """ Should fail if packages are in different locations. """
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id,
                          self.test_location_02.id,
                          4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        with self.assertRaises(ValidationError):
            picking.update_picking(
                package_name=SCANNED_PACKAGE_NAME,
                expected_package_names=[EXPECTED_PACKAGE_NAME])

    def test06_error_if_different_package_product(self):
        """ Should error if package products are different """
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)
        self.create_quant(self.banana.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        with self.assertRaises(ValidationError):
            picking.update_picking(
                package_name=SCANNED_PACKAGE_NAME,
                expected_package_names=[EXPECTED_PACKAGE_NAME])

    def test07_error_if_different_package_qty(self):
        """ Should error if products' qty are different """
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          8,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        with self.assertRaises(ValidationError):
            picking.update_picking(
                package_name=SCANNED_PACKAGE_NAME,
                expected_package_names=[EXPECTED_PACKAGE_NAME])

    def test08_error_if_different_picking_type(self):
        """
        Should error when swapping two packages:
         - with same contents;
         - in the same location;
         - both scanned and expected packages are reserved, but
           with different picking types.

        """
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        self.picking_type_internal.u_reserve_as_packages = True
        self.picking_type_internal.u_allow_swapping_packages = True
        self.create_picking(self.picking_type_internal,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)

        # checking pre-conditions
        self.assertTrue(self.scanned_package.is_reserved())
        self.assertTrue(self.expected_package.is_reserved())

        group = self.security_groups['outbound']
        group.u_picking_type_ids |= self.picking_type_internal

        with self.assertRaises(ValidationError):
            picking.update_picking(
                package_name=SCANNED_PACKAGE_NAME,
                expected_package_names=[EXPECTED_PACKAGE_NAME])

    def test09_error_if_different_picking_type_not_allowed(self):
        """
        Should error when swapping two packages:
         - with same contents;
         - in the same location;
         - both scanned and expected packages are reserved, but
           with different picking types, and not allowed to
           work with the second one.

        """
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.expected_package.id)
        self.create_quant(self.apple.id,
                          self.test_location_01.id,
                          4,
                          package_id=self.scanned_package.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        self.picking_type_internal.u_reserve_as_packages = True
        self.picking_type_internal.u_allow_swapping_packages = True
        self.picking_type_internal.default_location_src_id = \
            self.test_location_01.id
        self.create_picking(self.picking_type_internal,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)

        # checking pre-conditions
        self.assertTrue(self.scanned_package.is_reserved())
        self.assertTrue(self.expected_package.is_reserved())

        with self.assertRaises(ValidationError):
            picking.update_picking(
                package_name=SCANNED_PACKAGE_NAME,
                expected_package_names=[EXPECTED_PACKAGE_NAME])


class TestPackageContentsSwap(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.picking_type_internal.default_location_src_id = \
            cls.test_location_01.id

    def setUp(self):
        super().setUp()
        Package = self.env['stock.quant.package']

        self.picking_type_pick.u_reserve_as_packages = False
        self.picking_type_pick.u_user_scans = "product"
        self.picking_type_pick.u_allow_swapping_packages = True

        self.pack1 = Package.get_package("test_swap_pack1", create=True)
        self.pack2 = Package.get_package("test_swap_pack2", create=True)
        self.pack3 = Package.get_package("test_swap_pack3", create=True)
        self.pack4 = Package.get_package("test_swap_pack4", create=True)

    @classmethod
    def tearDownClass(cls):
        cls.picking_type_pick.u_user_scans = "package"
        super().tearDownClass()

    def _make_info(self, qty=10):
        return [{'product': self.apple, 'qty': qty}]

    def _make_pack_quant(self, pack, qty):
        self.create_quant(
            self.apple.id,
            self.test_location_01.id,
            qty,
            package_id=pack.id)

    def _make_pack1_quant(self):
        self._make_pack_quant(self.pack1, 10)

    def _make_pack2_quant(self):
        self._make_pack_quant(self.pack2, 3)

    def _make_pack3_quant(self):
        self._make_pack_quant(self.pack3, 3)

    def _make_pack4_quant(self):
        self._make_pack_quant(self.pack4, 4)

    def _check_unreserved(self, packs):
        self.assertFalse(
            any(p.is_reserved() for p in packs),
            "Package is not unreserved after swap")
        pack_quants = packs._get_contained_quants()
        self.assertEqual(sum(pack_quants.mapped("reserved_quantity")), 0,
                         "Got reserved quantities for unreserved packages")

    def _check_reserved(self, packs, qty=10):
        self.assertTrue(
            all(p.is_reserved() for p in packs),
            "Package is not reserved after swap")
        pack_quants = packs._get_contained_quants()
        self.assertEqual(sum(pack_quants.mapped("reserved_quantity")), qty,
                         "Expected quantity not reserved for packages")

    @staticmethod
    def _get_pack_mls(picking, packs):
        return picking.move_line_ids.filtered(lambda ml: ml.package_id in packs)

    def test01_multiple_to_one_when_one_is_unreserved(self):
        """Package should be swapped
        - Reserve packs 2, 3 & 4
        - Swap 2, 3 & 4 for pack 1
        - check packs 2, 3 & 4 are unreserved
        """
        self._make_pack2_quant()
        self._make_pack3_quant()
        self._make_pack4_quant()
        expected = self.pack2 | self.pack3 | self.pack4
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(10),
                                      confirm=True,
                                      assign=True)

        picking = picking.sudo(self.outbound_user)

        self._make_pack1_quant()

        # checking pre-conditions
        self.assertFalse(self.pack1.is_reserved())
        self.assertTrue(all(p.is_reserved() for p in expected))

        # method under test
        picking.update_picking(package_name=self.pack1.name,
                               expected_package_names=expected.mapped("name"))

        # checking outcome
        self._check_unreserved(expected)
        self._check_reserved(self.pack1, 10)

        expected_mls = self._get_pack_mls(picking, expected)
        scanned_mls = self._get_pack_mls(picking, self.pack1)
        self.assertEqual(len(expected_mls), 0,
                         "Got move lines related to the expected package")
        self.assertTrue(scanned_mls, "Move lines don't point to scanned package")

    def test02_error_when_expected_package_not_in_picking(self):
        """Should error when swapping pack 2 package pack 3 when pack 3 isn't
        in the picking
        """
        self._make_pack2_quant()
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(3),
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        self._make_pack3_quant()

        # checking pre-conditions
        self.assertTrue(self.pack2.is_reserved())
        self.assertFalse(self.pack3.is_reserved())

        with self.assertRaises(ValidationError) as err:
            picking.update_picking(
                package_name=self.pack2.name,
                expected_package_names=[self.pack3.name])

        self.assertEqual(
            err.exception.name,
            "Expected package(s) cannot be found in picking %s" % picking.name)



    def test03_multiple_to_one_when_all_are_reserved(self):
        """Package should be swapped
        - Reserve packs 1, 2, 3 & 4
        - Swap 2, 3 & 4 for pack 1
        - Check all packs are still reserved
        """
        self._make_pack2_quant()
        self._make_pack3_quant()
        self._make_pack4_quant()
        expected = self.pack2 | self.pack3 | self.pack4
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(10),
                                      confirm=True,
                                      assign=True)

        picking = picking.sudo(self.outbound_user)

        self._make_pack1_quant()
        _picking = self.create_picking(self.picking_type_pick,
                                       products_info=self._make_info(10),
                                       confirm=True,
                                       assign=True)

        # checking pre-conditions
        self.assertTrue(self.pack1.is_reserved())
        self.assertTrue(all(p.is_reserved() for p in expected))

        # method under test
        picking.update_picking(package_name=self.pack1.name,
                               expected_package_names=expected.mapped("name"))

        # checking outcome
        self._check_reserved(expected, 10)
        self._check_reserved(self.pack1, 10)

        expected_mls = self._get_pack_mls(picking, expected)
        scanned_mls = self._get_pack_mls(picking, self.pack1)
        self.assertEqual(len(expected_mls), 0,
                         "Got move lines related to the expected package")
        self.assertTrue(scanned_mls, "Move lines don't point to scanned package")

    def test04_one_to_multiple_when_multiple_is_unreserved(self):
        """Package should be swapped
        - Reserve pack 1
        - Swap 1 for pack 2, 3 & 4
        - Check pack 1 is unreserved
        """
        self._make_pack1_quant()
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(10),
                                      confirm=True,
                                      assign=True)

        picking = picking.sudo(self.outbound_user)

        self._make_pack2_quant()
        self._make_pack3_quant()
        self._make_pack4_quant()
        scanned = self.pack2 | self.pack3 | self.pack4

        # checking pre-conditions
        self.assertTrue(self.pack1.is_reserved())
        self.assertFalse(any(p.is_reserved() for p in scanned))

        # method under test
        for scanned_pack in scanned:
            picking.update_picking(package_name=scanned_pack.name,
                                   expected_package_names=[self.pack1.name])

        # checking outcome
        self._check_unreserved(self.pack1)
        self._check_reserved(scanned, 10)

        expected_mls = self._get_pack_mls(picking, self.pack1)
        scanned_mls = self._get_pack_mls(picking, scanned)
        self.assertEqual(len(expected_mls), 0,
                         "Got move lines related to the expected package")
        self.assertTrue(scanned_mls, "Move lines don't point to scanned package")

    def test05_one_to_multiple_when_multiple_is_partly_reserved(self):
        """Package should be swapped
        - Reserve packs 1 & 2
        - Swap 1 for pack 2, 3 & 4
        - Check pack 1 is reserved for quantity of pack 2
        """
        self._make_pack1_quant()
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(10),
                                      confirm=True,
                                      assign=True)

        picking = picking.sudo(self.outbound_user)

        self._make_pack2_quant()
        _picking = self.create_picking(self.picking_type_pick,
                                products_info=self._make_info(3),
                                confirm=True,
                                assign=True)

        self._make_pack3_quant()
        self._make_pack4_quant()

        # checking pre-conditions
        self.assertTrue(self.pack1.is_reserved())
        self.assertTrue(self.pack2.is_reserved())
        self.assertFalse(any(p.is_reserved() for p in self.pack3 | self.pack4))

        scanned = self.pack2 | self.pack3 | self.pack4
        # method under test
        for scanned_pack in scanned:
            picking.update_picking(package_name=scanned_pack.name,
                                   expected_package_names=[self.pack1.name])

        # checking outcome
        self._check_reserved(self.pack1, 3)
        self._check_reserved(scanned, 10)

        expected_mls = self._get_pack_mls(picking, self.pack1)
        scanned_mls = self._get_pack_mls(picking, scanned)
        self.assertEqual(len(expected_mls), 0,
                         "Got move lines related to the expected package")
        self.assertTrue(scanned_mls, "Move lines don't point to scanned package")

    def test06_one_to_part_of_one_and_multiple(self):
        """Part swap packages
        - Reserve packs 1 & 2
        - Partly swap 1 for pack 4
        - Check pack 1 and pack 4 is reserved for total quantity of pack 1
        """
        self._make_pack1_quant()
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(10),
                                      confirm=True,
                                      assign=True)

        picking = picking.sudo(self.outbound_user)
        self._make_pack4_quant()

        # checking pre-conditions
        self.assertTrue(self.pack1.is_reserved())
        self.assertFalse(self.pack4.is_reserved())

        # method under test
        picking.update_picking(package_name=self.pack4.name,
                               expected_package_names=[self.pack1.name])
        picking.update_picking(package_name=self.pack1.name)

        # checking outcome
        self._check_reserved(self.pack1 | self.pack4, 10)

        expected_mls = self._get_pack_mls(picking, self.pack1)
        scanned_mls = self._get_pack_mls(picking, self.pack4)
        self.assertTrue(expected_mls,
                        "Not found move lines related to the expected package")
        self.assertTrue(scanned_mls, "Move lines don't point to scanned package")

    def test07_one_to_part_of_one_and_multiple_when_one_is_part_reserved(self):
        """Part swap packages
        - Part reserve packs 1
        - Partly swap 1 for pack 4
        - Check pack 1 and pack 4 is reserved for the quantity pack 1 was
          originally reserved for
        """
        self._make_pack1_quant()
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(7),
                                      confirm=True,
                                      assign=True)

        picking = picking.sudo(self.outbound_user)

        self._make_pack4_quant()

        # checking pre-conditions
        self.assertTrue(self.pack1.is_reserved())
        self.assertFalse(self.pack4.is_reserved())

        # method under test
        picking.update_picking(package_name=self.pack4.name,
                               expected_package_names=[self.pack1.name])
        picking.update_picking(package_name=self.pack1.name)

        # checking outcome
        self._check_reserved(self.pack1 | self.pack4, 7)

        expected_mls = self._get_pack_mls(picking, self.pack1)
        scanned_mls = self._get_pack_mls(picking, self.pack4)
        self.assertTrue(expected_mls,
                        "Not found move lines related to the expected package")
        self.assertTrue(scanned_mls, "Move lines don't point to scanned package")

    def test07_swap_two_packs_for_part_package_which_is_less_that_total(self):
        """Part swap packages

        """
        self._make_pack_quant(self.pack1, 50)
        self._make_pack_quant(self.pack2, 50)
        self._make_pack_quant(self.pack3, 80)

        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(100),
                                      confirm=True,
                                      assign=True)

        product_ids = [{"barcode": self.apple.barcode, "qty": 50}]

        picking.update_picking(
            package_name=self.pack3.name,
            expected_package_names=[self.pack1.name, self.pack2.name],
            product_ids=product_ids
        )

        # Don't know which pack is fully swapped so lets grab them from picking
        reserved_packs = picking.move_line_ids.mapped("package_id")
        picking.update_picking(
            package_name=self.pack1.name,
            expected_package_names=reserved_packs.mapped("name"),
            product_ids=product_ids
        )

    def test08_swap_quantity_within_expected(self):
        """Part swap packages"""
        self._make_pack3_quant()
        self._make_pack4_quant()

        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(4),
                                      confirm=True,
                                      assign=True)

        picking.update_picking(
            package_name=self.pack4.name,
            expected_package_names=[self.pack3.name, self.pack4.name],
            product_ids=[{"barcode": self.apple.barcode, "qty": 4}]
        )
        self.assertFalse(self.pack3.is_reserved())
        self._check_reserved(self.pack4, 4)

    def test09_swap_quantity_within_expected_reserved_for_other_as_well(self):
        """Part swap packages"""
        self._make_pack3_quant()
        self._make_pack4_quant()

        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self._make_info(4),
                                      confirm=True,
                                      assign=True)

        self.create_picking(self.picking_type_pick,
                            products_info=self._make_info(3),
                            confirm=True,
                            assign=True)

        picking.update_picking(
            package_name=self.pack4.name,
            expected_package_names=[self.pack3.name, self.pack4.name],
            product_ids=[{"barcode": self.apple.barcode, "qty": 4}]
        )
        self.assertTrue(self.pack3.is_reserved())
        self._check_reserved(self.pack4, 4)
