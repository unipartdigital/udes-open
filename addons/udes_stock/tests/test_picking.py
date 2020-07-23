# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import ValidationError

class TestGoodsInPicking(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInPicking, cls).setUpClass()
        Picking = cls.env['stock.picking']
        products_info = [{'product': cls.apple, 'qty': 10}]
        cls.test_picking = cls.create_picking(cls.picking_type_in,
                                              origin="test_picking_origin",
                                              products_info=products_info,
                                              confirm=True)
        cls.SudoPicking = Picking.sudo(cls.inbound_user)
        cls.test_picking = cls.test_picking.sudo(cls.inbound_user)
        cls.tangerine_lot = cls.create_lot(cls.tangerine.id, 1)

    def generate_picks_and_pallets_for_check_entire_pack(self):
        """
            Generate picks and pallets for ready for_check_entire_pack function
        """
        Package = self.env['stock.quant.package']
        mummy_pallet = Package.get_package('mummy_pallet', create=True)
        baby_pallet = Package.get_package('baby_pallet', create=True)
        baby_pallet.package_id = mummy_pallet.id
        pick_product_info = [{'product': self.tangerine, 'qty': 10}]
        pick = self.create_picking(
            self.picking_type_in,
            origin="test_picking_origin",
            products_info=pick_product_info,
            confirm=True
        )
        pick.move_line_ids.result_package_id = baby_pallet.id
        pick.move_line_ids.qty_done = 10
        pick.move_line_ids.lot_id = self.tangerine_lot.id
        return mummy_pallet, pick

    def test01_get_pickings_by_package_name_fail(self):
        """ Tests get_pickings by package_name
            when no package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(package_name='DUMMY')
        self.assertEqual(len(returned_pickings), 0)

    def test02_get_pickings_by_package_name_sucess(self):
        """ Tests get_pickings by package_name
            when package exists
        """
        Package = self.env['stock.quant.package']
        test_package = Package.get_package('test_package', create=True)
        self.test_picking.move_line_ids.result_package_id = test_package
        returned_pickings = self.SudoPicking.get_pickings(package_name='test_package')
        self.assertEqual(returned_pickings.id, self.test_picking.id)

    def test03_get_pickings_by_origin_fail(self):
        """ Tests get_pickings by origin
            when no package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(origin='DUMMY')
        self.assertEqual(len(returned_pickings), 0)

    def test04_get_pickings_by_origin_sucess(self):
        """ Tests get_pickings by origin
            when package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(origin=self.test_picking.origin)
        self.assertEqual(returned_pickings.id, self.test_picking.id)

    def test05_get_info_all(self):
        """ Tests get_info without requesting
            a field
        """
        info = self.test_picking.get_info()
        expected = ['backorder_id',
                    'id',
                    'location_dest_id',
                    'moves_lines',
                    'name',
                    'origin',
                    'picking_type_id',
                    'priority',
                    'priority_name',
                    'state',
                    'picking_guidance'
        ]
        # Sorted returns a list(or did when I wrote this)
        # so no need to type cast
        self.assertEqual(sorted(info[0].keys()), sorted(expected))

    def test06_get_info_only_id(self):
        """ Tests get_info requesting a specific field"""
        info = self.test_picking.get_info(fields_to_fetch=['id'])
        # There should only be one and they should all be the same if not
        self.assertEqual(list(info[0].keys()), ['id'])

    def test07_get_priorities(self):
        """ Tests get_priorities by trivially exercising it """
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
        move_d12.move_orig_ids = (move_b1 | move_b2 | move_c3)
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
            self.assertEqual(e.exception.name, "Pickings stored by product cannot be inside packages.")

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

class TestSuggestedLocation(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        """Setup test data to test suggested locations."""
        super(TestSuggestedLocation, cls).setUpClass()

        Location = cls.env['stock.location']

        cls.test_location_03 = Location.create({
            "name": "Test location 03",
            "barcode": "LTEST03",
            "location_id": cls.stock_location.id,
        })
        cls.test_location_04 = Location.create({
            "name": "Test location 04",
            "barcode": "LTEST04",
            "location_id": cls.stock_location.id,
        })
        cls.test_locations += cls.test_location_03 + cls.test_location_04

        cls.test_stock_quant_01 = cls.create_quant(
            cls.tangerine.id,
            cls.test_location_01.id,
            10,
            "TESTLOT001"
        )
        cls.test_stock_quant_02 = cls.create_quant(
            cls.tangerine.id,
            cls.test_location_02.id,
            10,
            "TESTLOT002"
        )
        # Create a non-lot tracked quant
        cls.test_stock_quant_03 = cls.create_quant(
            cls.apple.id,
            cls.test_location_03.id,
            10,
        )

        # Create a new lot tracked product
        cls.uglyfruit = cls.create_product('Ugly Fruit', tracking='lot')

    def create_and_assign_putaway_picking(
        self,
        products_info,
        drop_policy="exactly_match_move_line"
    ):
        """Create and assign a putaway picking with associated quants created."""
        for info in products_info:
            test_quant = self.create_quant(
                info["product"].id,
                self.received_location.id,
                info["qty"],
            )
            # Remove lot from dictionary (if present) so that it may be used in create_picking
            lot = info.pop("lot", False)
            if lot:
                test_quant.lot_id = lot

        self.picking_type_putaway.u_drop_location_policy = drop_policy
        picking = self.create_picking(self.picking_type_putaway,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      assign=True)
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
            {"product": self.tangerine, "qty": 10, "lot": self.test_stock_quant_02.lot_id}
        ]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        # Assert that suggesting locations raises an error
        self.assertEqual(len(picking.move_line_ids), 2)
        with self.assertRaises(ValidationError) as e:
            picking.get_suggested_locations(picking.move_line_ids)
            self.assertEqual(
                e.exception.name,
                "Expecting a single lot number "
                "when dropping by product and lot."
            )

    def test04_get_suggested_location_by_product_lot_multiple_products(self):
        """Test that an error is raised if we want to suggest a location
        based on product and lot if there are multiple products in the picking.
        """
        drop_policy = "by_product_lot"
        uf_lot = self.create_lot(self.uglyfruit.id, "TEST_UF_LOT001")
        products_info = [
            {"product": self.tangerine, "qty": 10, "lot": self.test_stock_quant_01.lot_id},
            {"product": self.uglyfruit, "qty": 10, "lot": uf_lot}
        ]
        picking = self.create_and_assign_putaway_picking(products_info, drop_policy)

        # Assert that suggesting locations raises an error
        with self.assertRaises(ValidationError) as e:
            picking.get_suggested_locations(picking.move_line_ids)
            self.assertEqual(
                e.exception.name,
                "Cannot drop different products by lot number."
            )

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
        Location = self.env['stock.location']

        drop_policy = "by_height_speed"
        products_info = [{"product": self.apple, "qty": 10}]
        self.product_category_slow = self.create_category(name='Slow')
        self.product_category_ground = self.create_category(name='Ground')
        self.apple.u_height_category_id = self.product_category_ground
        self.apple.u_speed_category_id = self.product_category_slow

        # We need another empty location
        self.test_location_05 = Location.create({
            "name": "Test location 05",
            "barcode": "LTEST05",
            "location_id": self.stock_location.id,
        })

        picking1 = self.create_and_assign_putaway_picking(products_info, drop_policy)
        picking2 = self.create_and_assign_putaway_picking(products_info, drop_policy)
        picking1.apply_drop_location_policy()
        picking1.move_lines[0].product_uom_qty += 1
        self.assertEqual(picking1.move_line_ids.state, 'partially_available')

        suggested_locations = picking2.get_suggested_locations(picking2.move_line_ids)

        self.assertNotIn(picking1.move_line_ids.location_dest_id, suggested_locations)
        self.assertEqual(suggested_locations, self.test_location_05)
