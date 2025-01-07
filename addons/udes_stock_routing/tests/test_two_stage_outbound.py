from odoo.addons.udes_stock.tests.common import BaseUDES


class TwoStageOutboundBase(BaseUDES):
    @classmethod
    def setUpClass(cls):
        """
        Modify the BaseUDES Location structure to be useful for a two stage process.
        This involves doing the following;
        - Move existing stock locations to a new parent location of 'Normal' locations
        - Add the special staging locations to a sublocation of normal locations
        - Add the special locations (where two stage will be enabled) to a sublocation of stock, separate from normal locations.

        Any Pick pickings stock that is reserved under Special Locations should normally be destined for check locations.
        These will be split into two pickings:
        Stage 1:
          Special location --> Special staging location
        Stage 2:
          Special staging location --> Check (original destination)

        The reason the locations need to be separated in this way is to ensure users are not
        suggested 'Special' locations as part of normal processes.

        Location structure after this class has run (relevant location changes only):
        WH
        ├── TEST_CHECK
        │   ├── Test Check location 01
        │   └── Test Check location 02
        └── TEST_STOCK
            ├── TEST_SPECIAL
            │   ├── Test Special Location 01
            │   └── Test Special Location 02
            └── TEST_NORMAL
                ├── Test stock location 01
                ├── Test stock location 02
                ├── Test stock location 03
                ├── Test stock location 04
                └── TEST_SPECIAL_STAGING
                    ├── Test Special Staging Location 01
                    └── Test Special Staging Location 02

        """
        super().setUpClass()

        Location = cls.env["stock.location"]
        IrModuleModule = cls.env["ir.module.module"]

        cls.normal_location = Location.create(
            {
                "name": "TEST_NORMAL",
                "barcode": "LTESTNORMAL",
                "location_id": cls.stock_location.id,
                "usage": "view",
            }
        )
        # Update the existing test stock locations to live under TEST_NORMAL
        cls.test_stock_locations.write({"location_id": cls.normal_location.id})

        # Create the special and special staging view locations
        cls.special_staging_location = Location.create(
            {
                "name": "TEST_SPECIAL_STAGING",
                "barcode": "LTESTSPECIALSTAGING",
                "location_id": cls.normal_location.id,
                "usage": "view",
            }
        )
        cls.special_location = Location.create(
            {
                "name": "TEST_SPECIAL",
                "barcode": "LTESTSPECIAL",
                "location_id": cls.stock_location.id,
                "usage": "view",
                "u_requires_two_stage_when_stock_reserved": True,
                "u_two_stage_intermediate_location": cls.special_staging_location.id,
                # NOTE: u_two_stage_intermediate_dest_location does not need to be set
                # if the destination location of the original picking wants to be preserved.
                "u_two_stage_intermediate_operation_type": cls.picking_type_internal.id,
            }
        )

        # Create the special and special staging test locations
        cls.test_special_location_01 = Location.create(
            {
                "name": "Test Special Location 01",
                "barcode": "LTESTSPECIAL01",
                "location_id": cls.special_location.id,
                "usage": "internal",
            }
        )
        cls.test_special_location_02 = Location.create(
            {
                "name": "Test Special Location 02",
                "barcode": "LTESTSPECIAL02",
                "location_id": cls.special_location.id,
                "usage": "internal",
            }
        )

        cls.test_special_staging_location_01 = Location.create(
            {
                "name": "Test Special Staging Location 01",
                "barcode": "LTESTSPECIALSTAGING01",
                "location_id": cls.special_staging_location.id,
                "usage": "internal",
            }
        )
        cls.test_special_staging_location_02 = Location.create(
            {
                "name": "Test Special Staging Location 02",
                "barcode": "LTESTSPECIALSTAGING02",
                "location_id": cls.special_staging_location.id,
                "usage": "internal",
            }
        )
        cls.products_info = [
            {"product": cls.apple, "uom_qty": 10},
            {"product": cls.banana, "uom_qty": 5},
        ]
        cls.Picking = cls.env["stock.picking"]


class TestTwoStageOutbound(TwoStageOutboundBase):
    def test_two_stage_no_trigger_simple(self):
        """
        u_requires_two_stage_when_stock_reserved is off on Test stock location 01/02 and its parent(s).
        Therefore, no two stage process should be initialised when the stock is reserved from this location.
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 10)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 5)
        original_pick = self.create_picking(
            self.picking_type_pick, products_info=self.products_info, confirm=True, assign=True
        )
        self.assertEqual(original_pick.state, "assigned")
        self.assertEqual(original_pick.u_next_picking_ids.picking_type_id, self.picking_type_check)

    def test_two_stage_trigger_simple(self):
        """
        u_requires_two_stage_when_stock_reserved is enabled on Test Special Location 01/02's parent location.
        Therefore, a two stage process should be initialised when the stock is reserved from this location.

        Simple scenario - no mixed picking. 1 Pick --> 2 Picks
        """
        self.create_quant(self.apple.id, self.test_special_location_01.id, 10)
        self.create_quant(self.banana.id, self.test_special_location_02.id, 5)
        self.create_picking(
            self.picking_type_pick, products_info=self.products_info, confirm=True, assign=True
        )
        all_picks = self.Picking.search([])
        # The 2 stage process is configured to use the internal transfer picking type on self.special_location
        stage_1_pick = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids and p.picking_type_id == self.picking_type_internal
        )
        # The stage 1 pick should have its destination location swapped out.
        self.assertEqual(
            stage_1_pick.location_dest_id, self.special_location.u_two_stage_intermediate_location
        )
        # In this case, the configured operation type is internal transfer.
        self.assertEqual(
            stage_1_pick.picking_type_id,
            self.special_location.u_two_stage_intermediate_operation_type,
        )
        # The stock should be re-reserved immediately on the stage 1 pick.
        self.assertEqual(stage_1_pick.state, "assigned")
        # The picking type of the next picking should no longer be the Check picking, instead it is the 2nd stage,
        # which will preserve the original picking type.
        stage_2_pick = stage_1_pick.u_next_picking_ids
        self.assertEqual(stage_2_pick.picking_type_id, self.picking_type_pick)
        # It should be waiting for another operation
        self.assertEqual(stage_2_pick.state, "waiting")
        # The next picking of _that_ picking should be Check though
        check_pick = stage_2_pick.u_next_picking_ids
        self.assertEqual(check_pick.state, "waiting")
        self.assertEqual(check_pick.picking_type_id, self.picking_type_check)
        # Assert the 2nd stage pick source location is the configured u_two_stage_intermediate_location
        self.assertEqual(
            stage_2_pick.location_id, self.special_location.u_two_stage_intermediate_location
        )
        # Assert the 2nd stage pick destination is the same as the destination of the original pick would have been,
        # as u_two_stage_intermediate_dest_location is unconfigured.
        self.assertEqual(stage_2_pick.location_dest_id, self.check_location)

        # Assert the moves match the original on both stages (full pick has 1st 2nd stage applied)
        stage_1_apple_line = stage_1_pick.move_lines.filtered(lambda m: m.product_id == self.apple)
        stage_1_banana_line = stage_1_pick.move_lines.filtered(
            lambda m: m.product_id == self.banana
        )
        self.assertEqual(stage_1_apple_line.product_uom_qty, 10)
        self.assertEqual(stage_1_banana_line.product_uom_qty, 5)
        stage_2_apple_line = stage_2_pick.move_lines.filtered(lambda m: m.product_id == self.apple)
        stage_2_banana_line = stage_2_pick.move_lines.filtered(
            lambda m: m.product_id == self.banana
        )
        self.assertEqual(stage_2_apple_line.product_uom_qty, 10)
        self.assertEqual(stage_2_banana_line.product_uom_qty, 5)
        # Assert move dest links
        self.assertEqual(stage_1_apple_line.move_dest_ids, stage_2_apple_line)
        self.assertEqual(stage_1_banana_line.move_dest_ids, stage_2_banana_line)

        # Assert that the picks can be completed in succession
        self.complete_picking(stage_1_pick)
        self.assertEqual(stage_2_pick.state, "assigned")
        self.assertEqual(check_pick.state, "waiting")
        self.complete_picking(stage_2_pick)
        self.assertEqual(check_pick.state, "assigned")

    def test_two_stage_trigger_simple_mixed_with_normal_stock(self):
        """
        u_requires_two_stage_when_stock_reserved is enabled on Test Special Location 01/02's parent location.
        Therefore, a two stage process should be initialised when the stock is reserved from this location.
        However, the stock is reserved on a picking with normal stock also reserved - therefore the normal
        stock should stay in a picking effectively the same as the original picking (minus the two stage stock.)

        Simple scenario - mixed picking. 1 Pick --> 3 Picks
        """
        self.create_quant(self.apple.id, self.test_special_location_01.id, 10)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 5)
        self.create_picking(
            self.picking_type_pick, products_info=self.products_info, confirm=True, assign=True
        )
        all_picks = self.Picking.search([])
        stage_1_pick = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids and p.picking_type_id == self.picking_type_internal
        )
        self.assertEqual(
            stage_1_pick.location_dest_id, self.special_location.u_two_stage_intermediate_location
        )
        self.assertEqual(
            stage_1_pick.picking_type_id,
            self.special_location.u_two_stage_intermediate_operation_type,
        )
        self.assertEqual(stage_1_pick.state, "assigned")
        stage_2_pick = stage_1_pick.u_next_picking_ids
        self.assertEqual(stage_2_pick.picking_type_id, self.picking_type_pick)
        self.assertEqual(stage_2_pick.state, "waiting")
        check_pick = stage_2_pick.u_next_picking_ids
        self.assertEqual(check_pick.state, "waiting")
        self.assertEqual(check_pick.picking_type_id, self.picking_type_check)
        self.assertEqual(
            stage_2_pick.location_id, self.special_location.u_two_stage_intermediate_location
        )
        self.assertEqual(stage_2_pick.location_dest_id, self.check_location)

        # Assert the moves match only the ones which required a 2 stage split.
        stage_1_apple_line = stage_1_pick.move_lines.filtered(lambda m: m.product_id == self.apple)
        stage_1_banana_line = stage_1_pick.move_lines.filtered(
            lambda m: m.product_id == self.banana
        )
        self.assertEqual(stage_1_apple_line.product_uom_qty, 10)
        self.assertEqual(stage_1_banana_line.id, False)
        stage_2_apple_line = stage_2_pick.move_lines.filtered(lambda m: m.product_id == self.apple)
        stage_2_banana_line = stage_2_pick.move_lines.filtered(
            lambda m: m.product_id == self.banana
        )
        self.assertEqual(stage_2_apple_line.product_uom_qty, 10)
        self.assertEqual(stage_2_banana_line.id, False)

        self.assertEqual(stage_1_apple_line.move_dest_ids, stage_2_apple_line)
        self.assertEqual(stage_1_banana_line.move_dest_ids, stage_2_banana_line)

        # Assert the 'normal' pick remains ready to pick and still has a next picking as before.
        normal_pick = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids and p.picking_type_id == self.picking_type_pick
        )
        self.assertEqual(normal_pick.state, "assigned")
        normal_pick_banana_line = normal_pick.move_lines.filtered(
            lambda m: m.product_id == self.banana
        )
        self.assertEqual(normal_pick_banana_line.product_uom_qty, 5)
        self.assertEqual(normal_pick_banana_line.location_id, self.stock_location)
        self.assertEqual(normal_pick_banana_line.location_dest_id, self.check_location)
        self.assertEqual(normal_pick.u_next_picking_ids, stage_2_pick.u_next_picking_ids)

        # Assert that the picks can be completed in succession
        self.complete_picking(stage_1_pick)
        self.assertEqual(stage_2_pick.state, "assigned")
        self.assertEqual(check_pick.state, "waiting")
        self.complete_picking(stage_2_pick)
        check_pick = stage_2_pick.u_next_picking_ids
        self.complete_picking(normal_pick)
        self.assertTrue(check_pick.id)
        self.assertEqual(len(check_pick.move_line_ids), 2)
        self.assertEqual(check_pick.state, "assigned")

    def test_two_stage_trigger_complex(self):
        """
        u_requires_two_stage_when_stock_reserved is enabled on Test Special Location 01's parent location.
        It is also enabled on Test Special Location 02. This means the configuration on 02 will take precedence
        over its parents configuration for the stock reserved in that location.
        Therefore, multiple two stage processes should be initialised when the stock is reserved from these locations.

        Complex scenario - no mixed picking. 1 Pick --> 4 Picks
        """
        # This isn't a totally realistic configuration,
        # but it provides something different from that of the parent location.
        self.test_special_location_02.write(
            {
                "u_requires_two_stage_when_stock_reserved": True,
                "u_two_stage_intermediate_location": self.test_stock_location_04.id,
                "u_two_stage_intermediate_dest_location": self.test_check_location_01.id,
                "u_two_stage_intermediate_operation_type": self.picking_type_pick.id,
            }
        )
        self.create_quant(self.apple.id, self.test_special_location_01.id, 10)
        self.create_quant(self.banana.id, self.test_special_location_02.id, 5)
        self.create_picking(
            self.picking_type_pick, products_info=self.products_info, confirm=True, assign=True
        )

        all_picks = self.Picking.search([])

        stage_1_pick_apple = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids
            and p.picking_type_id == self.picking_type_internal
            and p.state == "assigned"
        )
        stage_1_pick_banana = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids
            and p.picking_type_id == self.picking_type_pick
            and p.state == "assigned"
        )
        # Mostly same assertions as the simple scenario, just on 2 sets of picks now.
        self.assertEqual(
            stage_1_pick_apple.location_dest_id,
            self.special_location.u_two_stage_intermediate_location,
        )
        self.assertEqual(
            stage_1_pick_banana.location_dest_id,
            self.test_special_location_02.u_two_stage_intermediate_location,
        )

        self.assertEqual(
            stage_1_pick_apple.picking_type_id,
            self.special_location.u_two_stage_intermediate_operation_type,
        )
        self.assertEqual(
            stage_1_pick_banana.picking_type_id,
            self.test_special_location_02.u_two_stage_intermediate_operation_type,
        )

        stage_2_pick_apple = stage_1_pick_apple.u_next_picking_ids
        stage_2_pick_banana = stage_1_pick_banana.u_next_picking_ids
        self.assertEqual(stage_2_pick_apple.picking_type_id, self.picking_type_pick)
        self.assertEqual(stage_2_pick_banana.picking_type_id, self.picking_type_pick)

        self.assertEqual(stage_2_pick_apple.state, "waiting")
        self.assertEqual(stage_2_pick_banana.state, "waiting")

        check_pick = stage_2_pick_apple.u_next_picking_ids | stage_2_pick_banana.u_next_picking_ids
        self.assertEqual(check_pick.state, "waiting")
        self.assertEqual(check_pick.picking_type_id, self.picking_type_check)

        self.assertEqual(
            stage_2_pick_apple.location_id, self.special_location.u_two_stage_intermediate_location
        )
        self.assertEqual(
            stage_2_pick_banana.location_id,
            self.test_special_location_02.u_two_stage_intermediate_location,
        )

        self.assertEqual(stage_2_pick_apple.location_dest_id, self.check_location)
        self.assertEqual(stage_2_pick_banana.location_dest_id, self.test_check_location_01)

        stage_1_apple_line = stage_1_pick_apple.move_lines
        stage_1_banana_line = stage_1_pick_banana.move_lines
        self.assertEqual(stage_1_apple_line.product_uom_qty, 10)
        self.assertEqual(stage_1_banana_line.product_uom_qty, 5)
        stage_2_apple_line = stage_2_pick_apple.move_lines
        stage_2_banana_line = stage_2_pick_banana.move_lines
        self.assertEqual(stage_2_apple_line.product_uom_qty, 10)
        self.assertEqual(stage_2_banana_line.product_uom_qty, 5)
        self.assertEqual(stage_1_apple_line.move_dest_ids, stage_2_apple_line)
        self.assertEqual(stage_1_banana_line.move_dest_ids, stage_2_banana_line)

        # Assert that the picks can be completed in succession
        self.complete_picking(stage_1_pick_apple)
        self.complete_picking(stage_1_pick_banana)
        self.assertEqual(stage_2_pick_apple.state, "assigned")
        self.assertEqual(stage_2_pick_banana.state, "assigned")
        self.assertEqual(check_pick.state, "waiting")
        self.complete_picking(stage_2_pick_apple)
        self.complete_picking(stage_2_pick_banana)
        check_pick = stage_2_pick_apple.u_next_picking_ids
        self.assertTrue(check_pick.id)

    def test_two_stage_trigger_complex_mixed_with_normal_stock(self):
        """
        u_requires_two_stage_when_stock_reserved is enabled on Test Special Location 01's parent location.
        It is also enabled on Test Special Location 02. This means the configuration on 02 will take precedence over 01
        for the stock reserved in that location.
        Therefore, a two stage process should be initialised when the stock is reserved from these locations.
        However, the stock is reserved on a picking with normal stock also reserved - therefore the normal
        stock should stay in a picking effectively the same as the original picking (minus the two stage stock.)

        Complex scenario - mixed picking. 1 Pick --> 5 Picks
        """
        self.test_special_location_02.write(
            {
                "u_requires_two_stage_when_stock_reserved": True,
                "u_two_stage_intermediate_location": self.test_stock_location_04.id,
                "u_two_stage_intermediate_dest_location": self.test_check_location_01.id,
                "u_two_stage_intermediate_operation_type": self.picking_type_pick.id,
            }
        )
        new_products_info = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 5},
            {"product": self.cherry, "uom_qty": 2},
        ]
        self.create_quant(self.apple.id, self.test_special_location_01.id, 10)
        self.create_quant(self.banana.id, self.test_special_location_02.id, 5)
        self.create_quant(self.cherry.id, self.test_stock_location_01.id, 2)
        self.create_picking(
            self.picking_type_pick, products_info=new_products_info, confirm=True, assign=True
        )

        all_picks = self.Picking.search([])

        stage_1_pick_apple = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids and p.picking_type_id == self.picking_type_internal
        )
        # The original pick is also a pick picking type, and has 'normal' stock (cherry) on it.
        # An easy way to tell the difference is by using u_from_two_stage_split.
        stage_1_pick_banana = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids
            and p.picking_type_id == self.picking_type_pick
            and p.u_from_two_stage_split == True
        )
        # Mostly same assertions as the simple scenario, just on 2 sets of picks now.
        self.assertEqual(
            stage_1_pick_apple.location_dest_id,
            self.special_location.u_two_stage_intermediate_location,
        )
        self.assertEqual(
            stage_1_pick_banana.location_dest_id,
            self.test_special_location_02.u_two_stage_intermediate_location,
        )

        self.assertEqual(
            stage_1_pick_apple.picking_type_id,
            self.special_location.u_two_stage_intermediate_operation_type,
        )
        self.assertEqual(
            stage_1_pick_banana.picking_type_id,
            self.test_special_location_02.u_two_stage_intermediate_operation_type,
        )

        self.assertEqual(stage_1_pick_apple.state, "assigned")
        self.assertEqual(stage_1_pick_banana.state, "assigned")

        stage_2_pick_apple = stage_1_pick_apple.u_next_picking_ids
        stage_2_pick_banana = stage_1_pick_banana.u_next_picking_ids
        self.assertEqual(stage_2_pick_apple.picking_type_id, self.picking_type_pick)
        self.assertEqual(stage_2_pick_banana.picking_type_id, self.picking_type_pick)

        self.assertEqual(stage_2_pick_apple.state, "waiting")
        self.assertEqual(stage_2_pick_banana.state, "waiting")

        check_pick = stage_2_pick_apple.u_next_picking_ids | stage_2_pick_banana.u_next_picking_ids
        self.assertEqual(check_pick.state, "waiting")
        self.assertEqual(check_pick.picking_type_id, self.picking_type_check)

        self.assertEqual(
            stage_2_pick_apple.location_id, self.special_location.u_two_stage_intermediate_location
        )
        self.assertEqual(
            stage_2_pick_banana.location_id,
            self.test_special_location_02.u_two_stage_intermediate_location,
        )

        self.assertEqual(stage_2_pick_apple.location_dest_id, self.check_location)
        self.assertEqual(stage_2_pick_banana.location_dest_id, self.test_check_location_01)

        normal_pick = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids
            and p.picking_type_id == self.picking_type_pick
            and p.u_from_two_stage_split == False
        )
        self.assertEqual(normal_pick.state, "assigned")
        normal_pick_cherry_line = normal_pick.move_lines.filtered(
            lambda m: m.product_id == self.cherry
        )
        self.assertEqual(normal_pick_cherry_line.product_uom_qty, 2)
        self.assertEqual(normal_pick_cherry_line.location_id, self.stock_location)
        self.assertEqual(normal_pick_cherry_line.location_dest_id, self.check_location)
        self.assertEqual(
            normal_pick.u_next_picking_ids,
            stage_2_pick_apple.u_next_picking_ids | stage_2_pick_banana.u_next_picking_ids,
        )

        stage_1_apple_line = stage_1_pick_apple.move_lines
        stage_1_banana_line = stage_1_pick_banana.move_lines
        self.assertEqual(stage_1_apple_line.product_uom_qty, 10)
        self.assertEqual(stage_1_banana_line.product_uom_qty, 5)
        stage_2_apple_line = stage_2_pick_apple.move_lines
        stage_2_banana_line = stage_2_pick_banana.move_lines
        self.assertEqual(stage_2_apple_line.product_uom_qty, 10)
        self.assertEqual(stage_2_banana_line.product_uom_qty, 5)
        self.assertEqual(stage_1_apple_line.move_dest_ids, stage_2_apple_line)
        self.assertEqual(stage_1_banana_line.move_dest_ids, stage_2_banana_line)

        # Assert that the picks can be completed in succession
        self.complete_picking(stage_1_pick_apple)
        self.complete_picking(stage_1_pick_banana)
        self.assertEqual(stage_2_pick_apple.state, "assigned")
        self.assertEqual(stage_2_pick_banana.state, "assigned")
        self.assertEqual(check_pick.state, "waiting")
        self.complete_picking(stage_2_pick_apple)
        self.complete_picking(stage_2_pick_banana)
        self.complete_picking(normal_pick)
        check_pick = stage_2_pick_apple.u_next_picking_ids
        self.assertTrue(check_pick.id)

    def test_two_stage_split_partial_reservation(self):
        """
        When a partial reservation occurs on a picking, and part of the reserved stock is in a 2 stage location,
        then the reserved stock should be split to 2 stage, while leaving the remainder on the original picking.
        """
        self.create_quant(self.apple.id, self.test_special_location_01.id, 1)  # 9 unfulfilled.
        # self.create_quant(self.apple.id, self.test_stock_location_01.id, 1)
        self.create_quant(self.banana.id, self.test_special_location_02.id, 5)
        self.create_picking(
            self.picking_type_pick, products_info=self.products_info, confirm=True, assign=True
        )
        all_picks = self.Picking.search([])
        # The 2 stage process is configured to use the internal transfer picking type on self.special_location
        stage_1_pick = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids and p.picking_type_id == self.picking_type_internal
        )
        self.assertTrue(stage_1_pick.id)
        self.assertEqual(len(stage_1_pick.move_line_ids), 2)
        stage_2_pick = stage_1_pick.u_next_picking_ids
        self.assertTrue(stage_2_pick.id)
        self.assertEqual(len(stage_2_pick.move_lines), 2)
        original_pick = stage_2_pick.backorder_id
        # The unfulfilled qty (9) of apples should be left on the original picking.
        self.assertEqual(len(original_pick.move_lines), 1)

    def test_two_stage_split_partial_reservation_with_normal_stock(self):
        """
        When a partial reservation occurs on a picking, and part of the reserved stock is in a 2 stage location,
        and part of the stock is reserved for a normal location, then the reserved stock should be split to 2 stage,
        while leaving the remainder on the original picking.
        """
        self.create_quant(self.apple.id, self.test_special_location_01.id, 1)  # 9 unfulfilled.
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 1)
        self.create_quant(self.banana.id, self.test_special_location_02.id, 5)
        self.create_picking(
            self.picking_type_pick, products_info=self.products_info, confirm=True, assign=True
        )
        all_picks = self.Picking.search([])
        # The 2 stage process is configured to use the internal transfer picking type on self.special_location
        stage_1_pick = all_picks.filtered(
            lambda p: not p.u_prev_picking_ids and p.picking_type_id == self.picking_type_internal
        )
        self.assertTrue(stage_1_pick.id)
        self.assertEqual(len(stage_1_pick.move_line_ids), 2)
        stage_2_pick = stage_1_pick.u_next_picking_ids
        self.assertTrue(stage_2_pick.id)
        self.assertEqual(len(stage_2_pick.move_lines), 2)
        original_pick = stage_2_pick.backorder_id
        # The unfulfilled qty (9) of apples should be left on the original picking.
        self.assertEqual(len(original_pick.move_lines), 1)
