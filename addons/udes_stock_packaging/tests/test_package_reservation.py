from odoo.exceptions import ValidationError
from odoo.addons.udes_stock.tests.common import BaseUDES


class TestPackageReservation(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestPackageReservation, cls).setUpClass()
        # enable full package reservation
        cls.picking_type_pick.u_reserve_as_packages = True

        cls.product_info = [{"product": cls.apple, "uom_qty": 1}]

    def test_reserve_full_package_one_product(self):
        """
        Test that the a package is fully reserved,
        even though a picking is requested a lower quantity
        """
        # create a package
        package = self.create_package()

        # create a quant of 4 apples in a stock sublocation for the package
        quant = self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=package.id
        )
        # the quant should be unreserved
        self.assertEqual(quant.reserved_quantity, 0)

        # create a Pick for 1 apple
        picking = self.create_picking(
            self.picking_type_pick, products_info=self.product_info, confirm=True, assign=False
        )

        picking.action_assign()

        move_count_pre_assign = len(picking.move_lines)

        # the quant should be fully reserved
        self.assertEqual(quant.reserved_quantity, 4)

        # apple stock.move.lines of the picking should have the package
        apple_mls = picking.move_line_ids
        self.assertEqual(apple_mls.package_id, package)

        # the apple move should still be present after unreserving
        picking.do_unreserve()
        move_count_post_unreserve = len(picking.move_lines)
        self.assertEqual(move_count_pre_assign, move_count_post_unreserve)

    def test_reserve_full_package_two_products(self):
        """
        Test to reserve a full package for one product
        when initial demand < package quantity
        """

        # create a package
        package = self.create_package()

        # create a quant of 3 apples in a stock sublocation for the package
        apple_quant = self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 3, package_id=package.id
        )
        strawberry_quant_1 = self.create_quant(
            self.strawberry.id,
            self.test_stock_location_01.id,
            1,
            package_id=package.id,
            lot_name="sn01",
        )
        strawberry_quant_2 = self.create_quant(
            self.strawberry.id,
            self.test_stock_location_01.id,
            1,
            package_id=package.id,
            lot_name="sn02",
        )
        all_quants = apple_quant + strawberry_quant_1 + strawberry_quant_2

        # all quants should be unreserved
        self.assertTrue(
            all([q.reserved_quantity == 0 for q in all_quants]), "One or more quants are reserved"
        )

        for q in all_quants:
            with self.subTest(quant_id=q.id):
                self.assertEqual(q.reserved_quantity, 0)

        # create a Pick for 1 apple
        picking = self.create_picking(
            self.picking_type_pick, products_info=self.product_info, confirm=True, assign=False
        )

        move_count_pre_assign = len(picking.move_lines)
        picking.action_assign()

        # apple quant should be fully reserved
        self.assertEqual(apple_quant.reserved_quantity, 3)
        # strawberry quants should be fully reserved
        self.assertEqual(strawberry_quant_1.reserved_quantity, 1)
        self.assertEqual(strawberry_quant_2.reserved_quantity, 1)

        # apple stock.move.lines of the picking should have the package
        apple_mls = picking.move_line_ids.filtered(lambda ml: ml.product_id == self.apple)
        self.assertEqual(apple_mls.package_id, package)

        # strawberry stock.move.lines of the picking should have the package
        strawberry_mls = picking.move_line_ids.filtered(lambda ml: ml.product_id == self.strawberry)
        self.assertEqual(strawberry_mls.package_id, package)

        # picking should have only the original removes remaining after unreserving,
        # as extra products from full package reservation should have been removed
        picking.do_unreserve()
        move_count_post_unreserve = len(picking.move_lines)
        self.assertEqual(move_count_pre_assign, move_count_post_unreserve)

    def test_partial_reservation_package_one_still_functional(self):
        """
        Test to reserve a full package for one product
        when initial demand < package quantity
        """

        # disable full package reservation
        self.picking_type_pick.u_reserve_as_packages = False

        # create a package
        package = self.create_package()

        # create a quant of 4 apples in a stock sublocation for the package
        quant = self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=package.id
        )
        # the quant should be unreserved
        self.assertEqual(quant.reserved_quantity, 0, "The quant is reserved")

        # create a Pick for 1 apple
        picking = self.create_picking(
            self.picking_type_pick, products_info=self.product_info, confirm=True, assign=True
        )

        # the quant should be partially reserved
        self.assertEqual(quant.reserved_quantity, 1)

        # apple stock.move.lines of the picking should have the package
        apple_mls = picking.move_line_ids.filtered(lambda ml: ml.product_id == self.apple)
        self.assertEqual(apple_mls.package_id, package)

        # update_picking with package_name = package.name should raise an error
        with self.assertRaises(ValidationError) as e:
            package.assert_reserved_full_package(apple_mls)
        self.assertEqual(
            e.exception.args[0], f"Cannot mark partially reserved package {package.name} as done."
        )

    def test_multiple_pickings_do_not_block_each_other_doing_full_package_reservation(self):
        """Test the case when there is more than one picking in the set being reserved."""

        # create stock of 2 products, in package, to reserve.
        apple_pack = self.create_package()
        apple_quant = self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=apple_pack.id
        )

        banana_pack = self.create_package()
        banana_quant = self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 4, package_id=banana_pack.id
        )
        self.assertEqual(apple_quant.reserved_quantity, 0)
        self.assertEqual(banana_quant.reserved_quantity, 0)

        # create two picks for 1 of each product
        self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "uom_qty": 1}],
            confirm=True,
            assign=True,
        )
        self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.banana, "uom_qty": 1}],
            confirm=True,
            assign=True,
        )

        # both quants should be fully reserved
        self.assertEqual(apple_quant.reserved_quantity, 4)
        self.assertEqual(banana_quant.reserved_quantity, 4)

    def test_initial_demand_and_product_quantity(self):
        """
        Test the initial demand is set to the first product quantity value.
        When unreserving test that the extra quantity added by full package reservation
        is removed from the product quantity.
        """

        # create stock of 1 product, in package, to reserve.
        apple_pack = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=apple_pack.id
        )

        # create a pick for 1 apple
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "uom_qty": 1}],
            confirm=True,
            assign=False,
        )

        move = pick.move_lines
        # initial demand should match product quantity.
        self.assertEqual(move.u_uom_initial_demand, move.product_uom_qty)

        pick.action_assign()

        # initial demand should not match product quantity due to full package reservation.
        self.assertNotEqual(move.u_uom_initial_demand, move.product_uom_qty)

        pick.do_unreserve()

        # product quantity should revert back to initial demand.
        self.assertEqual(move.u_uom_initial_demand, move.product_uom_qty)
