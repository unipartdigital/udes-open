# -*- coding: utf-8 -*-
from . import common
from odoo.exceptions import ValidationError


class TestGoodsInPicking(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestGoodsInPicking, cls).setUpClass()
        Picking = cls.env["stock.picking"]
        products_info = [{"product": cls.apple, "qty": 10}]
        cls.picking_type_in.u_handle_partials = True
        cls.test_picking = cls.create_picking(
            cls.picking_type_in,
            origin="test_picking_origin",
            products_info=products_info,
            confirm=True,
        )
        cls.SudoPicking = Picking.sudo(cls.inbound_user)
        cls.test_picking = cls.test_picking.sudo(cls.inbound_user)
        cls.tangerine_lot = cls.create_lot(cls.tangerine.id, 1)

    def generate_picks_and_pallets_for_check_entire_pack(self):
        """
        Generate picks and pallets for ready for_check_entire_pack function
        """
        Package = self.env["stock.quant.package"]
        mummy_pallet = Package.get_package("mummy_pallet", create=True)
        baby_pallet = Package.get_package("baby_pallet", create=True)
        baby_pallet.package_id = mummy_pallet.id
        pick_product_info = [{"product": self.tangerine, "qty": 10}]
        pick = self.create_picking(
            self.picking_type_in,
            origin="test_picking_origin",
            products_info=pick_product_info,
            confirm=True,
        )
        pick.move_line_ids.result_package_id = baby_pallet.id
        pick.move_line_ids.qty_done = 10
        pick.move_line_ids.lot_id = self.tangerine_lot.id
        return mummy_pallet, pick

    def test01_get_pickings_by_package_name_fail(self):
        """Tests get_pickings by package_name
        when no package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(package_name="DUMMY")
        self.assertEqual(len(returned_pickings), 0)

    def test02_get_pickings_by_package_name_sucess(self):
        """Tests get_pickings by package_name
        when package exists
        """
        Package = self.env["stock.quant.package"]
        test_package = Package.get_package("test_package", create=True)
        self.test_picking.move_line_ids.result_package_id = test_package
        returned_pickings = self.SudoPicking.get_pickings(package_name="test_package")
        self.assertEqual(returned_pickings.id, self.test_picking.id)

    def test03_get_pickings_by_origin_fail(self):
        """Tests get_pickings by origin
        when no package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(origin="DUMMY")
        self.assertEqual(len(returned_pickings), 0)

    def test04_get_pickings_by_origin_sucess(self):
        """Tests get_pickings by origin
        when package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(origin=self.test_picking.origin)
        self.assertEqual(len(returned_pickings), 2)
        self.assertTrue(self.test_picking in returned_pickings)

    def test05_get_info_all(self):
        """Tests get_info without requesting
        a field
        """
        info = self.test_picking.get_info()
        expected = [
            "backorder_id",
            "id",
            "location_dest_id",
            "moves_lines",
            "name",
            "origin",
            "picking_type_id",
            "priority",
            "priority_name",
            "state",
            "picking_guidance",
            "u_original_picking_id",
        ]
        # Sorted returns a list(or did when I wrote this)
        # so no need to type cast
        self.assertEqual(sorted(info[0].keys()), sorted(expected))

    def test06_get_info_only_id(self):
        """Tests get_info requesting a specific field"""
        info = self.test_picking.get_info(fields_to_fetch=["id"])
        # There should only be one and they should all be the same if not
        self.assertEqual(list(info[0].keys()), ["id"])

    def test07_get_priorities(self):
        """Tests get_priorities by trivially exercising it"""
        priorities = self.SudoPicking.get_priorities()
        self.assertNotEqual(priorities, [])

    def test08_related_pickings(self):
        """Test first/previous/next picking calculations"""
        pick_a = self.create_picking(self.picking_type_internal)
        move_a1 = self.create_move(self.apple, 1, pick_a)
        pick_b = self.create_picking(self.picking_type_internal)
        move_b1 = self.create_move(self.apple, 1, pick_b)
        move_b1.move_orig_ids = move_a1
        move_b2 = self.create_move(self.apple, 9, pick_b)
        pick_c = self.create_picking(self.picking_type_internal)
        move_c3 = self.create_move(self.apple, 5, pick_c)
        pick_d = self.create_picking(self.picking_type_internal)
        move_d12 = self.create_move(self.apple, 15, pick_d)
        move_d12.move_orig_ids = move_b1 | move_b2 | move_c3
        self.assertFalse(pick_a.u_prev_picking_ids)
        self.assertEqual(pick_a.u_next_picking_ids, pick_b)
        self.assertEqual(pick_b.u_prev_picking_ids, pick_a)
        self.assertEqual(pick_b.u_next_picking_ids, pick_d)
        self.assertEqual(pick_d.u_prev_picking_ids, (pick_b | pick_c))
        self.assertFalse(pick_d.u_next_picking_ids)
        self.assertEqual(pick_a.u_first_picking_ids, pick_a)
        self.assertEqual(pick_b.u_first_picking_ids, (pick_a | pick_b))
        self.assertEqual(pick_d.u_first_picking_ids, (pick_a | pick_b | pick_c))

    def test09_pallets_of_packages_have_parent_package(self):
        """
         Test that only pallets of packages have a parent package added by
        _check_entire_pack/_set_u_result_parent_package_id
        """

        self.picking_type_in.u_target_storage_format = "pallet_packages"
        pallet, pick = self.generate_picks_and_pallets_for_check_entire_pack()
        pick._check_entire_pack()
        self.assertEqual(pallet, pick.move_line_ids.u_result_parent_package_id)

    def test10_product_packages_has_no_parent_package(self):
        """
         Test that only product have a parent package added by
        _check_entire_pack/_set_u_result_parent_package_id
        """

        self.picking_type_in.u_target_storage_format = "product"
        with self.assertRaises(ValidationError) as e:
            _, pick = self.generate_picks_and_pallets_for_check_entire_pack()
            self.assertEqual(
                e.exception.name, "Pickings stored by product cannot be inside packages."
            )

    def test11_pallet_of_products_has_no_parent_package(self):
        """
         Test that only product have a parent package added by
        _check_entire_pack/_set_u_result_parent_package_id
        """

        self.picking_type_in.u_target_storage_format = "pallet_products"
        _, pick = self.generate_picks_and_pallets_for_check_entire_pack()
        pick._check_entire_pack()
        self.assertFalse(pick.move_line_ids.u_result_parent_package_id)

    def test12_package_has_no_parent_package(self):
        """
         Test that only product have a parent package added by
        _check_entire_pack/_set_u_result_parent_package_id
        """

        self.picking_type_in.u_target_storage_format = "pallet_products"
        _, pick = self.generate_picks_and_pallets_for_check_entire_pack()
        pick._check_entire_pack()
        self.assertFalse(pick.move_line_ids.u_result_parent_package_id)

    def test13_pallet_of_packages_has_no_parent_package_if_user_scans_is_package(self):
        """
         Test that only product have a parent package added by
        _check_entire_pack/_set_u_result_parent_package_id
        """

        self.picking_type_in.u_target_storage_format = "pallet_packages"
        self.picking_type_in.u_user_scans = "package"
        _, pick = self.generate_picks_and_pallets_for_check_entire_pack()
        pick._check_entire_pack()
        self.assertFalse(pick.move_line_ids.u_result_parent_package_id)

    def test14_original_picking_information_is_as_expected(self):
        """
        Check that the original picking information is propgated down.
        Pick 2 items at a time until everything is picked.
        """
        picking = self.test_picking
        prod_barcode = picking.move_line_ids.product_id.barcode
        for idx in range(5):
            with self.subTest(idx=idx):
                self.assertEqual(picking.state, "assigned")
                self.assertEqual(picking.u_original_picking_id, self.test_picking)
                package = self.create_package()
                picking.update_picking(
                    location_dest_id=self.received_location.id,
                    validate=True,
                    result_package_name=package.name,
                    product_ids=[{"barcode": prod_barcode, "qty": 2}],
                    create_backorder=idx < 4,
                )
                self.assertEqual(picking.state, "done")
                self.assertEqual(picking.move_lines.state, "done")
                self.assertEqual(picking.move_lines.product_uom_qty, 2)
                if idx < 4:
                    picking = picking.u_created_back_orders
                    self.assertTrue(picking)
                else:
                    self.assertFalse(picking.u_created_back_orders)


class TestProcessPartial(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestProcessPartial, cls).setUpClass()
        products_info = [{"product": cls.apple, "qty": 10}]
        cls.picking_type_in.u_handle_partials = True
        cls.picking_type_in.u_user_process_partial = True
        cls.picking = cls.create_picking(
            cls.picking_type_in, origin="test_origin", products_info=products_info, confirm=True
        )

    def test_simple_u_user_process_partial(self):
        """
        Test when u_user_process_partial is enabled then when the picking has
        something completed, the picking information gets placed in a backorder.
        """
        prod_barcode = self.picking.move_line_ids.product_id.barcode
        for idx in range(1, 5):
            with self.subTest(idx=idx):
                self.assertEqual(self.picking.state, "assigned")
                package = self.create_package()
                self.picking.update_picking(
                    location_dest_id=self.received_location.id,
                    validate=True,
                    result_package_name=package.name,
                    product_ids=[{"barcode": prod_barcode, "qty": idx}],
                )
                if idx < 4:
                    # The done picking is placed into a backorder
                    completed_backorders = self.picking.u_created_back_orders
                    self.assertEqual(len(completed_backorders), idx)
                    # Check the last done picking is as expected
                    last_completed_picking = completed_backorders.filtered(
                        lambda p: p.move_lines.product_uom_qty == idx
                    )
                    self.assertTrue(last_completed_picking)
                    self.assertEqual(last_completed_picking.backorder_id, self.picking)
                    self.assertEqual(last_completed_picking.u_original_picking_id, self.picking)

        # Check everything at the end is as expected
        # I.e the original picing is done and maps to all the backorders
        self.assertEqual(self.picking.state, "done")
        self.assertEqual(self.picking.move_lines.product_uom_qty, 4)
        self.assertFalse(self.picking.backorder_id)
        backorders = self.picking.u_created_back_orders
        self.assertEqual(len(backorders), 3)
        self.assertEqual(backorders.mapped("state"), 3 * ["done"])
        self.assertEqual(backorders.mapped("move_lines.product_uom_qty"), [1, 2, 3])
        self.assertEqual(backorders.mapped("backorder_id"), self.picking)
        self.assertEqual(backorders.mapped("u_original_picking_id"), self.picking)


class TestSuggestedLocation(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        """Setup test data to test suggested locations."""
        super(TestSuggestedLocation, cls).setUpClass()

        Location = cls.env["stock.location"]

        cls.test_location_03 = Location.create(
            {"name": "Test location 03", "barcode": "LTEST03", "location_id": cls.stock_location.id}
        )
        cls.test_location_04 = Location.create(
            {"name": "Test location 04", "barcode": "LTEST04", "location_id": cls.stock_location.id}
        )
        cls.test_locations += cls.test_location_03 + cls.test_location_04

        cls.test_stock_quant_01 = cls.create_quant(
            cls.tangerine.id, cls.test_location_01.id, 10, "TESTLOT001"
        )
        cls.test_stock_quant_02 = cls.create_quant(
            cls.tangerine.id, cls.test_location_02.id, 10, "TESTLOT002"
        )
        # Create a non-lot tracked quant
        cls.test_stock_quant_03 = cls.create_quant(cls.apple.id, cls.test_location_03.id, 10)

        # Create a new lot tracked product
        cls.uglyfruit = cls.create_product("Ugly Fruit", tracking="lot")

    def create_and_assign_putaway_picking(
        self, products_info, drop_policy="exactly_match_move_line"
    ):
        """Create and assign a putaway picking with associated quants created."""
        for info in products_info:
            test_quant = self.create_quant(
                info["product"].id, self.received_location.id, info["qty"]
            )
            # Remove lot from dictionary (if present) so that it may be used in create_picking
            lot = info.pop("lot", False)
            if lot:
                test_quant.lot_id = lot

        self.picking_type_putaway.u_drop_location_policy = drop_policy
        picking = self.create_picking(
            self.picking_type_putaway,
            origin="test_picking_origin",
            products_info=products_info,
            assign=True,
        )
        picking = picking.sudo(self.inbound_user)
        return picking

    def test01_get_suggested_location_by_product_lot(self):
        """Test that we can obtain the correct sugested location when
        suggesting by product and lot.
        """
        drop_policy = "by_product_lot"
        products_info = [
            {"product": self.tangerine, "qty": 10, "lot": self.test_stock_quant_01.lot_id}
        ]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        suggested_locations = picking.get_suggested_locations(picking.move_line_ids)

        # Assert that only a single location is returned;
        # the location with the matching product and lot.
        self.assertEqual(len(suggested_locations), 1)
        self.assertTrue(self.test_location_01 in suggested_locations)
        # To be thorough, test that a location with the same product
        # but different lot is not returned.
        self.assertFalse(self.test_location_02 in suggested_locations)

    def test02_get_suggested_location_by_product_lot_no_match(self):
        """Test that empty locations are returned when there are no suitable
        locations when suggesting by product and lot.
        """
        drop_policy = "by_product_lot"
        uf_lot = self.create_lot(self.uglyfruit.id, "TEST_UF_LOT001")
        products_info = [{"product": self.uglyfruit, "qty": 10, "lot": uf_lot}]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        suggested_locations = picking.get_suggested_locations(picking.move_line_ids)

        # Assert that only a single location is returned;
        # the empty location.
        self.assertEqual(len(suggested_locations), 1)
        self.assertTrue(self.test_location_04 in suggested_locations)

    def test03_get_suggested_location_by_product_lot_multiple_lots(self):
        """Test that an error is raised if we want to suggest a location
        based on product and lot if there are multiple lots in the picking.
        """
        drop_policy = "by_product_lot"
        products_info = [
            {"product": self.tangerine, "qty": 10, "lot": self.test_stock_quant_01.lot_id},
            {"product": self.tangerine, "qty": 10, "lot": self.test_stock_quant_02.lot_id},
        ]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        # Assert that suggesting locations raises an error
        self.assertEqual(len(picking.move_line_ids), 2)
        with self.assertRaises(ValidationError) as e:
            picking.get_suggested_locations(picking.move_line_ids)
            self.assertEqual(
                e.exception.name,
                "Expecting a single lot number " "when dropping by product and lot.",
            )

    def test04_get_suggested_location_by_product_lot_multiple_products(self):
        """Test that an error is raised if we want to suggest a location
        based on product and lot if there are multiple products in the picking.
        """
        drop_policy = "by_product_lot"
        uf_lot = self.create_lot(self.uglyfruit.id, "TEST_UF_LOT001")
        products_info = [
            {"product": self.tangerine, "qty": 10, "lot": self.test_stock_quant_01.lot_id},
            {"product": self.uglyfruit, "qty": 10, "lot": uf_lot},
        ]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        # Assert that suggesting locations raises an error
        with self.assertRaises(ValidationError) as e:
            picking.get_suggested_locations(picking.move_line_ids)
            self.assertEqual(e.exception.name, "Cannot drop different products by lot number.")

    def test05_get_suggested_location_by_product_lot_not_tracked(self):
        """Test that when a product is not lot tracked, locations of that product
        are returned.
        """
        drop_policy = "by_product_lot"
        products_info = [{"product": self.apple, "qty": 10}]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        suggested_locations = picking.get_suggested_locations(picking.move_line_ids)

        # Assert that only a single location is returned;
        # the location with the matching product.
        self.assertEqual(len(suggested_locations), 1)
        self.assertTrue(self.test_location_03 in suggested_locations)

    def test06_get_suggested_location_by_product(self):
        """Test that we can obtain the correct sugested location when
        suggesting by product.
        """
        drop_policy = "by_products"
        products_info = [{"product": self.apple, "qty": 10}]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        suggested_locations = picking.get_suggested_locations(picking.move_line_ids)

        # Assert that only a single location is returned;
        # the location with the matching product.
        self.assertEqual(len(suggested_locations), 1)
        self.assertTrue(self.test_location_03 in suggested_locations)

    def test07_get_suggested_location_by_product_no_match(self):
        """Test that empty locations are returned when there are no suitable
        locations when suggesting by product.
        """
        drop_policy = "by_products"
        products_info = [{"product": self.banana, "qty": 10}]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        suggested_locations = picking.get_suggested_locations(picking.move_line_ids)

        # Assert that only a single location is returned;
        # the empty location.
        self.assertEqual(len(suggested_locations), 1)
        self.assertTrue(self.test_location_04 in suggested_locations)

    def test08_get_suggested_location_by_product_all_lots(self):
        """Test that we can obtain all locations for a lot tracked product when
        suggesting by product.
        """
        drop_policy = "by_products"
        products_info = [
            {"product": self.tangerine, "qty": 10, "lot": self.test_stock_quant_01.lot_id}
        ]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        suggested_locations = picking.get_suggested_locations(picking.move_line_ids)

        # Assert that two locations are returned;
        # the location with the matching product and lot
        # and the location with matching product but different lot.
        self.assertEqual(len(suggested_locations), 2)
        self.assertEqual(self.test_location_01 + self.test_location_02, suggested_locations)

    def test09_considers_partially_available_move_lines_when_suggesting_location(self):
        """Test that we don't suggest locations associated with partially
        available move lines.
        """
        Location = self.env["stock.location"]

        drop_policy = "by_height_speed"
        products_info = [{"product": self.apple, "qty": 10}]
        self.product_category_slow = self.create_category(name="Slow")
        self.product_category_ground = self.create_category(name="Ground")
        self.apple.u_height_category_id = self.product_category_ground
        self.apple.u_speed_category_id = self.product_category_slow

        # We need another empty location
        self.test_location_05 = Location.create(
            {
                "name": "Test location 05",
                "barcode": "LTEST05",
                "location_id": self.stock_location.id,
            }
        )

        picking1 = self.create_and_assign_putaway_picking(products_info, drop_policy)
        picking2 = self.create_and_assign_putaway_picking(products_info, drop_policy)
        picking1.apply_drop_location_policy()
        picking1.move_lines[0].product_uom_qty += 1
        self.assertEqual(picking1.move_line_ids.state, "partially_available")

        suggested_locations = picking2.get_suggested_locations(picking2.move_line_ids)

        self.assertNotIn(picking1.move_line_ids.location_dest_id, suggested_locations)
        self.assertEqual(suggested_locations, self.test_location_05)


class TestPickingWarning(common.BaseUDES):
    """Test the generation of warning messages for user-set pre-conditions"""

    @classmethod
    def setUpClass(cls):
        super(TestPickingWarning, cls).setUpClass()
        Picking = cls.env["stock.picking"]

        cls.products_info = [{"product": cls.apple, "qty": 10}]
        cls.test_picking = cls.create_picking(
            cls.picking_type_in,
            origin="test_picking_origin",
            products_info=cls.products_info,
            confirm=True,
        )
        cls.next_picking = cls.test_picking.u_next_picking_ids
        # Setup picking type so that the pre-condition is met
        cls.next_picking.picking_type_id.u_warn_picking_precondition = "pickings_pending"
        cls.next_picking.picking_type_id.u_handle_partials = False
        cls.test_picking = cls.test_picking.sudo(cls.inbound_user)

    def test_doesnt_warn_picking_pickings_pending(self):
        """Assert that we don't get a warning message when checking if pickings are pending
        when condition isn't met.
        """
        # Get message for picking without previous picking
        self.assertFalse(
            self.test_picking.u_prev_picking_ids, "Assert there are no previous pickings"
        )
        message_not_pending = self.test_picking.warn_picking_pickings_pending()

        self.assertFalse(
            message_not_pending,
            "Assert a message is not returned when there are no previous pickings",
        )

    def test_warn_picking_pickings_pending(self):
        """Assert that we get a warning message when checking if pickings are pending
        when condition is met and no warning is given if it isn't.
        """
        # Get message for picking with previous picking
        message_pending = self.next_picking.warn_picking_pickings_pending()

        self.assertTrue(
            message_pending, "Assert a message is returned when previous pickings are incomplete"
        )
        self.assertIsInstance(message_pending, str)


class TestPickingLocked(common.BaseUDES):
    """Test that unlocked pickings are locked when confirmed or completed"""

    @classmethod
    def setUpClass(cls):
        super(TestPickingLocked, cls).setUpClass()

        cls.picking = cls.create_picking(cls.picking_type_in)
        cls.apple_qty = 10

    def test_assert_confirmed_unlocked_picking_locked(self):
        """Assert that an unlocked picking is locked once it has been confirmed."""
        # Create move for picking
        self.create_move(self.apple, self.apple_qty, self.picking)

        # Confirm picking and assert it has been locked
        self.picking.action_confirm()
        self.assertTrue(
            self.picking.is_locked, "Picking should have been locked after being confirmed"
        )

    def test_assert_completed_unlocked_picking_locked(self):
        """
        Assert that an unlocked picking with manually created move lines
        is locked once it has been completed.
        """
        MoveLine = self.env["stock.move.line"]

        # Manually create the move lines (allowed because picking is unlocked)
        move_line_vals = {
            "picking_id": self.picking.id,
            "location_id": self.picking.location_id.id,
            "location_dest_id": self.picking.location_dest_id.id,
            "product_id": self.apple.id,
            "product_uom_id": self.apple.uom_id.id,
            "product_uom_qty": self.apple_qty,
            "qty_done": self.apple_qty,
        }
        MoveLine.create(move_line_vals)

        # Mark picking as completed and assert it has been locked
        self.picking.action_done()

        self.assertTrue(
            self.picking.is_locked, "Picking should have been locked after being completed"
        )

    def test_creates_picking_unlocked_picking_by_default(self):
        """A newly created draft picking should be unlocked."""
        picking = self.create_picking(self.picking_type_in)
        self.assertFalse(
            picking.is_locked, "Picking should default to being unlocked at creation time"
        )

    def test_confirming_a_move_locks_the_picking(self):
        """Implicit confirmation should lock the picking."""
        # Create move for picking
        move = self.create_move(self.apple, self.apple_qty, self.picking)
        self.assertEqual(move.state, "draft")
        self.assertEqual(self.picking.state, "draft")

        # Confirm the move and assert the picking has been locked
        self.picking.move_lines._action_confirm()

        self.assertEqual(self.picking.state, "confirmed")
        self.assertTrue(
            self.picking.is_locked, "Picking should have been locked after its moves are  confirmed"
        )


class TestBatchUserName(common.BaseUDES):
    """Test Batch User takes value expected and changes when expected"""

    @classmethod
    def setUpClass(cls):
        super(TestBatchUserName, cls).setUpClass()
        cls.create_quant(cls.apple.id, cls.test_location_01.id, 10)

        cls.batch = cls.create_batch(user=cls.env.user)

        cls._pick_info = [{"product": cls.apple, "qty": 5}]
        cls.picking = cls.create_picking(
            picking_type=cls.picking_type_pick, products_info=cls._pick_info, confirm=True
        )

    def test_correct_batch_user_on_picking_tree_view(self):
        self.picking.write({"batch_id": self.batch.id})

        self.assertEqual(self.picking.u_batch_user_id, self.env.user)

    def test_no_batch_user_on_picking_when_no_batch(self):
        self.assertEqual(len(self.picking.u_batch_user_id), 0)

    def test_batch_user_on_picking_changes_when_user_is_changed_on_batch(self):
        self.picking.write({"batch_id": self.batch.id})

        self.batch.write({"user_id": self.stock_manager.id})

        self.assertEqual(self.picking.u_batch_user_id, self.stock_manager)

    def test_same_batch_user_on_multiple_pickings(self):
        picking_2 = self.create_picking(
            picking_type=self.picking_type_pick, products_info=self._pick_info, confirm=True
        )

        self.picking.write({"batch_id": self.batch.id})
        picking_2.write({"batch_id": self.batch.id})

        self.assertEqual(self.picking.u_batch_user_id, self.env.user)
        self.assertEqual(picking_2.u_batch_user_id, self.env.user)
