# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import ValidationError
from collections import Counter

class TestPackageReservation(common.BaseUDES):

    def test01_reserve_full_package_one_product(self):
        """ Test to reserve a full package for one product
            when initial demand < package quantity
        """
        Package = self.env['stock.quant.package']

        # enable full package reservation
        self.picking_type_pick.u_reserve_as_packages = True

        # create a package
        package = Package.get_package('test_package', create=True)

        # create a quant of 4 apples in a stock sublocation for the package
        quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                  4, package_id=package.id)
        # the quant should be unreserved
        self.assertEqual(quant.reserved_quantity, 0,
                         "The quant is reserved")

        # create a Pick for 1 apple
        create_info = [{'product': self.apple, 'qty': 1}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=create_info,
                                      confirm=True,
                                      assign=False)
        picking = picking.sudo(self.outbound_user)
        picking.action_assign()

        # the quant should be fully reserved
        self.assertEqual(quant.reserved_quantity, 4)

        # apple stock.move.lines of the picking should have the package
        apple_mls = picking.mapped('move_line_ids').filtered(lambda ml: ml.product_id == self.apple)
        self.assertTrue(all([ml.package_id == package for ml in apple_mls]))

    def test02_reserve_full_package_two_products(self):
        """ Test to reserve a full package for one product
            when initial demand < package quantity
        """
        Package = self.env['stock.quant.package']

        # enable full package reservation
        self.picking_type_pick.u_reserve_as_packages = True

        # create a package
        package = Package.get_package('test_package', create=True)

        # create a quant of 3 apples in a stock sublocation for the package
        apple_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                  3, package_id=package.id)
        sw_quant_1 = self.create_quant(self.strawberry.id, self.test_location_01.id,
                                  1, package_id=package.id, serial_number='sn01')
        sw_quant_2 = self.create_quant(self.strawberry.id, self.test_location_01.id,
                                  1, package_id=package.id, serial_number='sn02')
        all_quants = apple_quant + sw_quant_1 + sw_quant_2

        # all quants should be unreserved
        self.assertTrue(all([q.reserved_quantity == 0 for q in all_quants]),
                         "One or more quants are reserved")

        # create a Pick for 1 apple
        create_info = [{'product': self.apple, 'qty': 1}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=create_info,
                                      confirm=True,
                                      assign=False)
        picking = picking.sudo(self.outbound_user)
        picking.action_assign()

        # apple quant should be fully reserved
        self.assertEqual(apple_quant.reserved_quantity, 3)
        # strawberry quants should be fully reserved
        self.assertEqual(sw_quant_1.reserved_quantity, 1)
        self.assertEqual(sw_quant_2.reserved_quantity, 1)

        # apple stock.move.lines of the picking should have the package
        apple_mls = picking.mapped('move_line_ids').filtered(lambda ml: ml.product_id == self.apple)
        self.assertTrue(all([ml.package_id == package for ml in apple_mls]))

        # strawberry stock.move.lines of the picking should have the package
        sw_mls = picking.mapped('move_line_ids').filtered(lambda ml: ml.product_id == self.strawberry)
        self.assertTrue(all([ml.package_id == package for ml in apple_mls]))


    def test03_partially_reserve_package_one_product_error(self):
        """ Test to reserve a full package for one product
            when initial demand < package quantity
        """
        Package = self.env['stock.quant.package']

        # enable full package reservation
        self.picking_type_pick.u_reserve_as_packages = False

        # create a package
        package = Package.get_package('test_package', create=True)

        # create a quant of 4 apples in a stock sublocation for the package
        quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                  4, package_id=package.id)
        # the quant should be unreserved
        self.assertEqual(quant.reserved_quantity, 0,
                         "The quant is reserved")

        # create a Pick for 1 apple
        create_info = [{'product': self.apple, 'qty': 1}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=create_info,
                                      confirm=True,
                                      assign=False)
        picking = picking.sudo(self.outbound_user)
        picking.action_assign()

        # the quant should be partially reserved
        self.assertEqual(quant.reserved_quantity, 1)

        # apple stock.move.lines of the picking should have the package
        apple_mls = picking.mapped('move_line_ids').filtered(lambda ml: ml.product_id == self.apple)
        self.assertTrue(all([ml.package_id == package for ml in apple_mls]))

        # update_picking with package_name = package.name should raise an error
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(package_name=package.name)
        self.assertEqual(e.exception.name, 'Cannot mark as done a partially reserved package.')

    def test04_multiple_pickings(self):
        """Test the case when there is more than one picking in the set being reserved.
        This caused a bug where a package in Pick02 would prevent Pick01 from being
        rounded up, see #3453"""
        Package = self.env['stock.quant.package']

        # enable full package reservation
        self.picking_type_pick.u_reserve_as_packages = True

        # create stock of 2 products, in package, to reserve.
        apple_pack = Package.get_package('test_package1', create=True)
        apple_quant = self.create_quant(self.apple.id, self.test_location_01.id,
                                        4, package_id=apple_pack.id)

        banana_pack = Package.get_package('test_package2', create=True)
        banana_quant = self.create_quant(self.banana.id, self.test_location_01.id,
                                         4, package_id=banana_pack.id)
        self.assertEqual(apple_quant.reserved_quantity, 0)
        self.assertEqual(banana_quant.reserved_quantity, 0)

        # create a two picks for 1 of each product
        pick_1 = self.create_picking(self.picking_type_pick,
                                     products_info=[{'product': self.apple,
                                                     'qty': 1}],
                                     confirm=True,
                                     assign=False)
        pick_2 = self.create_picking(self.picking_type_pick,
                                     products_info=[{'product': self.banana,
                                                     'qty': 1}],
                                     confirm=True,
                                     assign=False)

        pickings = (pick_1 | pick_2).sudo(self.outbound_user)
        pickings.action_assign()

        # both quants should be fully reserved
        self.assertEqual(apple_quant.reserved_quantity, 4)
        self.assertEqual(banana_quant.reserved_quantity, 4)
