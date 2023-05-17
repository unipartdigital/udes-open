from odoo.addons.udes_stock.tests import common
from odoo.osv import expression
import random


class TestRefactoringBase(common.BaseUDES):
    def setUp(self):
        """
        Base test class for refactoring tests
        Create pick with test pick type
        Create pallets and quants for apples and banana products
        """
        super(TestRefactoringBase, self).setUp()

        self.picking = self.create_picking(self.picking_type_pick)

        # Setup pallets and quants for apple and banana products
        product_qty = 10

        self.apple_pallet = self.create_package()
        self.apple_quant = self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            product_qty,
            package_id=self.apple_pallet.id,
        )

        self.banana_pallet = self.create_package()
        self.banana_quant = self.create_quant(
            self.banana.id,
            self.test_stock_location_01.id,
            product_qty,
            package_id=self.banana_pallet.id,
        )

    @classmethod
    def get_move_lines_for_product(cls, product, picking_type=None, package=None, aux_domain=None):
        """
        Find and return all move lines in the system for a product.

        Optionally provide a picking type, package and aux_domain.

        Useful for retrieving move lines after a picking has been split via refactoring.
        """
        MoveLine = cls.env["stock.move.line"]

        product.ensure_one()

        domain = [("product_id", "=", product.id)]
        if picking_type:
            domain = expression.AND([domain, [("u_picking_type_id", "=", picking_type.id)]])
        if package:
            domain = expression.AND([domain, [("package_id", "=", package.id)]])
        if aux_domain:
            domain = expression.AND([domain, aux_domain])

        return MoveLine.search(domain)

    def _assert_move_fields(self, move, product, product_qty):
        """
        Assert that the supplied move line recordset has only 1 record.
        Assert that the move line has the expected product and product quantity
        """
        self.assertEqual(len(move), 1, "Should only be 1 move record")
        self.assertEqual(move.product_id, product, "Move product should match expected product")
        self.assertEqual(
            move.product_qty, product_qty, "Move quantity should match expected quantity"
        )

    def _assert_move_line_fields(self, move_line, product, product_qty, package):
        """
        Assert that the supplied move line recordset has only 1 record.
        Assert that the move line has the expected product, product quantity,
        package and result package
        """
        self.assertEqual(len(move_line), 1)
        self.assertEqual(move_line.product_id, product)
        self.assertEqual(move_line.product_qty, product_qty)
        self.assertEqual(move_line.package_id, package)
        self.assertEqual(move_line.result_package_id, package)

    def _assert_picking_fields(
        self,
        picking,
        state=None,
        origin=None,
        partner=None,
        group_name=None,
        location_id=None,
        location_dest_id=None,
        date_done=None,
        priority=None,
    ):
        """
        Assert that the supplied picking recordset has only 1 record.
        Assert that the state, origin, partner, group name, location,
        destination location and date done match the expected values
        if supplied.
        """
        self.assertEqual(len(picking), 1)
        self.assertFalse(picking.u_is_empty)

        if state:
            self.assertEqual(picking.state, state)
        if origin:
            self.assertEqual(picking.origin, origin)
        if partner:
            self.assertEqual(picking.partner_id, partner)
        if group_name:
            self.assertEqual(picking.group_id.name, group_name)
        if location_id:
            self.assertEqual(picking.location_id, location_id)
        if location_dest_id:
            self.assertEqual(picking.location_dest_id, location_dest_id)
        if date_done:
            self.assertEqual(picking.date_done, date_done)
        if priority:
            self.assertEqual(picking.priority, priority)

    def _assert_package_levels(self, pickings):
        """
        Assert that each supplied picking has package level records for any packages
        within the picking, and does not have any records for packages not in the picking.

        Also assert any move lines with a package on each picking have a package level set.
        """
        for picking in pickings:
            package_levels = picking.package_level_ids
            packages = picking.move_line_ids.package_id
            pl_packages = package_levels.package_id

            package_names = ",".join(package.name for package in packages)
            pl_package_names = ",".join(package.name for package in pl_packages)

            with self.subTest(packages=packages, pl_packages=pl_packages):
                self.assertEqual(
                    packages,
                    pl_packages,
                    f"Picking {picking.name} should have package levels for {package_names}, "
                    f"got: {pl_package_names}",
                )

            if package_levels:
                package_level_move_lines = package_levels.move_line_ids
                for move_line in picking.move_line_ids.filtered("package_id"):
                    with self.subTest(move_line=move_line):
                        prod_name = move_line.product_id.name
                        ml_qty = move_line.product_uom_qty
                        pack_name = move_line.package_id.name
                        ml_desc = f"{prod_name} x {ml_qty} ({pack_name})"
                        self.assertIn(
                            move_line,
                            package_level_move_lines,
                            f"Move Line {ml_desc} should have a package level set.",
                        )


class TestAssignRefactoring(TestRefactoringBase):
    def setUp(self):
        """
        Set post assign action for test pick type
        """
        # group by package post assign
        self.picking_type_pick.write(
            {
                "u_post_assign_action": "group_by_move_line_key",
                "u_move_line_key_format": "{package_id.name}",
            }
        )

        super(TestAssignRefactoring, self).setUp()

    def test_reserve_1_pallet_diff_prods_splits_1_pick_per_pallet(self):
        """
        With 1 pallet each for 2 different products.
        Reserve pick (action_assign).
        Pick should be split into 2 picks 1 for each pallet,
        reusing the original pick.
        """
        apple_pallet = self.apple_pallet
        banana_pallet = self.banana_pallet
        products_info = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 10},
        ]
        moves = self.create_move(self.picking, products_info)
        apple_move = moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = moves - apple_move
        self.picking.action_assign()
        self.assertFalse(self.picking.date_done)
        apple_pick = apple_move.picking_id
        banana_pick = banana_move.picking_id
        # Assert picking fields are correct. Having different group names ensures
        # apple_pick and banana_pick are not the same.
        self.assertFalse(apple_pick.date_done)
        self.assertFalse(banana_pick.date_done)
        self._assert_picking_fields(apple_pick, state="assigned", group_name=apple_pallet.name)
        self._assert_picking_fields(banana_pick, state="assigned", group_name=banana_pallet.name)
        # Check we haven't mangled the moves or move_lines
        apple_move = apple_pick.move_lines
        self._assert_move_fields(apple_move, self.apple, 10)
        apple_move_line = apple_pick.move_line_ids
        self._assert_move_line_fields(apple_move_line, self.apple, 10, apple_pallet)
        banana_move = banana_pick.move_lines
        self._assert_move_fields(banana_move, self.banana, 10)
        banana_move_line = banana_pick.move_line_ids
        self._assert_move_line_fields(banana_move_line, self.banana, 10, banana_pallet)
        # Check that the original pick has been reused
        self.assertTrue(self.picking.exists())
        original_picking_reused = self.picking in (apple_pick | banana_pick)
        self.assertTrue(original_picking_reused)

    def test_reserve_2_pallets_same_prods_splits_1_pick_per_pallet(self):
        """
        With 2 pallets that contains the same product.
        Reserve pick (action_assign).
        Pick should be split into 2 picks 1 for each pallet,
        reusing the original pick.
        """
        apple_pallet = self.apple_pallet
        other_apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=other_apple_pallet.id
        )
        products_info = [{"product": self.apple, "uom_qty": 20}]
        self.create_move(self.picking, products_info)
        self.picking.action_assign()
        apple_move_lines = self.get_move_lines_for_product(
            self.apple, picking_type=self.picking.picking_type_id
        )
        self.assertEqual(len(apple_move_lines), 2)
        apple_pallet_move_line = apple_move_lines.filtered(lambda ml: ml.package_id == apple_pallet)
        other_apple_pallet_move_line = apple_move_lines - apple_pallet_move_line
        apple_pick = apple_pallet_move_line.picking_id
        other_apple_pick = other_apple_pallet_move_line.picking_id
        self.assertFalse(apple_pick.date_done)
        self.assertFalse(other_apple_pick.date_done)
        refactored_picks = apple_pick | other_apple_pick
        # Assert picking fields are correct. Having different group names ensures
        # apple_pick and other_apple_pick are not the same.
        self._assert_picking_fields(apple_pick, state="assigned", group_name=apple_pallet.name)
        self._assert_picking_fields(
            other_apple_pick, state="assigned", group_name=other_apple_pallet.name
        )
        # Check we haven't mangled the moves or move_lines
        apple_pick_move = apple_pick.move_lines
        self._assert_move_fields(apple_pick_move, self.apple, 10)
        apple_pick_move_line = apple_pick.move_line_ids
        self._assert_move_line_fields(apple_pick_move_line, self.apple, 10, apple_pallet)
        other_apple_pick_move = other_apple_pick.move_lines
        self._assert_move_fields(other_apple_pick_move, self.apple, 10)
        other_apple_pick_move_line = other_apple_pick.move_line_ids
        self._assert_move_line_fields(
            other_apple_pick_move_line, self.apple, 10, other_apple_pallet
        )
        # Check that the package levels have been split
        self._assert_package_levels(refactored_picks)
        # Check that the original pick has been reused
        self.assertTrue(self.picking.exists())
        original_picking_reused = self.picking in refactored_picks
        self.assertTrue(original_picking_reused)

    def test_reserve_1_pallet_diff_prods_no_split(self):
        """
        With 1 pallet that contains different products.
        Reserve pick (action_assign).
        Original pick should be maintained.
        """
        fig = self.fig
        grape = self.grape

        mixed_pallet = self.create_package()
        self.create_quant(fig.id, self.test_stock_location_01.id, 5, package_id=mixed_pallet.id)
        self.create_quant(grape.id, self.test_stock_location_01.id, 10, package_id=mixed_pallet.id)
        products_info = [{"product": fig, "uom_qty": 5}, {"product": grape, "uom_qty": 10}]
        moves = self.create_move(self.picking, products_info)
        fig_move = moves.filtered(lambda m: m.product_id == fig)
        grape_move = moves - fig_move
        self.picking.action_assign()
        pick = (fig_move | grape_move).picking_id
        self._assert_picking_fields(pick, state="assigned", group_name=mixed_pallet.name)
        # Check we haven't mangled the moves or move_lines
        moves = pick.move_lines
        self.assertEqual(len(moves), 2)
        fig_move = moves.filtered(lambda m: m.product_id == fig)
        grape_move = moves - fig_move
        self.assertEqual(fig_move.product_uom_qty, 5)
        self.assertEqual(grape_move.product_uom_qty, 10)
        move_lines = pick.move_line_ids
        self.assertEqual(len(move_lines), 2)
        fig_moveline = move_lines.filtered(lambda ml: ml.product_id == fig)
        grape_moveline = move_lines - fig_moveline
        self._assert_move_line_fields(fig_moveline, fig, 5, mixed_pallet)
        self._assert_move_line_fields(grape_moveline, grape, 10, mixed_pallet)
        # Check that the original pick has been reused
        self.assertTrue(self.picking.exists())
        self.assertFalse(self.picking.date_done)

    def test_reserve_simultaneously_2_picks_1_pallet_same_prods_merges_1_pick(self):
        """
        With 2 picks for 2 of the same products on one pallet.
        Reserve both picks (action_assign) simultaneously.
        Original picks should be empty (u_is_empty field is set to True) and deleted.
        A new pick should be created with both the moves.
        """
        apple_pallet = self.apple_pallet
        self.apple_quant.quantity = 25
        pick1 = self.picking
        pick2 = self.create_picking(self.picking_type_pick)
        pick1_products_info = [{"product": self.apple, "uom_qty": 10}]
        move1 = self.create_move(pick1, pick1_products_info)
        pick2_products_info = [{"product": self.apple, "uom_qty": 15}]
        move2 = self.create_move(pick2, pick2_products_info)
        (pick1 | pick2).action_assign()
        pick = (move1 | move2).picking_id
        self._assert_picking_fields(pick, state="assigned", group_name=apple_pallet.name)
        # Check we haven't mangled the moves or move_lines
        self.assertEqual((move1 | move2), pick.move_lines)
        move_lines = pick.move_line_ids
        self.assertEqual(len(move_lines), 2)
        self.assertFalse(pick.date_done)
        move_line1 = move_lines.filtered(lambda ml: ml.move_id == move1)
        move_line2 = move_lines - move_line1
        self._assert_move_line_fields(move_line1, self.apple, 10, apple_pallet)
        self._assert_move_line_fields(move_line2, self.apple, 15, apple_pallet)
        # Check that neither pick has been reused, empty picks have been (u_is_empty = True)
        # and deleted at the very end of the action
        self.assertFalse(pick1.exists())
        self.assertFalse(pick2.exists())

    def test_reserve_sequentially_2_picks_1_pallet_same_prods_merges_1_pick(self):
        """
        With 2 picks for 2 of the same products on one pallet.
        Reserve both picks (action_assign) sequentially.
        Original picks should be empty (u_is_empty field is set to True) and deleted.
        A new pick should be created with both the moves.
        """
        apple_pallet = self.apple_pallet
        self.apple_quant.quantity = 25
        pick1 = self.picking
        pick2 = self.create_picking(self.picking_type_pick)
        pick1_products_info = [{"product": self.apple, "uom_qty": 10}]
        move1 = self.create_move(pick1, pick1_products_info)
        pick2_products_info = [{"product": self.apple, "uom_qty": 15}]
        move2 = self.create_move(pick2, pick2_products_info)
        pick1.action_assign()
        self.assertFalse(pick1.move_line_ids.mapped("result_package_id"))
        pick2.action_assign()
        self.assertTrue(pick1.move_line_ids.mapped("result_package_id"))
        pick = (move1 | move2).picking_id
        self._assert_picking_fields(pick, state="assigned", group_name=apple_pallet.name)
        # Check we haven't mangled the moves or move_lines
        self.assertEqual((move1 | move2), pick.move_lines)
        move_lines = pick.move_line_ids
        self.assertEqual(len(move_lines), 2)
        move_line1 = move_lines.filtered(lambda ml: ml.move_id == move1)
        move_line2 = move_lines - move_line1
        self._assert_move_line_fields(move_line1, self.apple, 10, apple_pallet)
        self._assert_move_line_fields(move_line2, self.apple, 15, apple_pallet)
        # Check that the first pick has been reused and the second pick is empty
        # (u_is_empty = True) and deleted at the very end of the action
        self.assertTrue(pick1.exists())
        self.assertFalse(pick1.date_done)
        self.assertFalse(pick2.exists())

    def test_reserve_1_prod_assert_non_default_locations_maintained(self):
        """
        With non-default locations set on pick.
        Reserve pick (action_assign).
        Non-default location fields should be maintained.
        """
        self.picking.write(
            {
                "location_id": self.test_stock_location_01.id,
                "location_dest_id": self.test_goodsout_location_01.id,
            }
        )

        products_info = [{"product": self.apple, "uom_qty": 10}]
        apple_move = self.create_move(self.picking, products_info)
        self.picking.action_assign()
        apple_pick = apple_move.picking_id
        # Check pick reuse
        self.assertEqual(self.picking, apple_pick)
        self.assertFalse(self.picking.date_done)
        # Check pick state, location and destination location
        self._assert_picking_fields(
            apple_pick,
            state="assigned",
            location_id=self.test_stock_location_01,
            location_dest_id=self.test_goodsout_location_01,
        )

    def test_package_levels_setup_after_split(self):
        """
        With 1 product being picked from 2 pallets.
        Reserve stock for the pick.
        Pick should be split into 2, with a package level for each pallet on each picking.
        """
        apple_pallet2 = self.create_package()
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            5,
            package_id=apple_pallet2.id,
        )
        products_info = [{"product": self.apple, "uom_qty": 15}]
        self.create_move(self.picking, products_info)
        self.picking.action_assign()

        pallet1_ml = self.get_move_lines_for_product(
            self.apple, picking_type=self.picking.picking_type_id, package=self.apple_pallet
        )
        pallet2_ml = self.get_move_lines_for_product(
            self.apple, picking_type=self.picking.picking_type_id, package=apple_pallet2
        )
        pallet1_picking = pallet1_ml.picking_id
        pallet2_picking = pallet2_ml.picking_id
        self._assert_package_levels(pallet1_picking | pallet2_picking)
        self.assertFalse(pallet1_picking.date_done)
        self.assertFalse(pallet2_picking.date_done)

    def test_package_levels_setup_after_merge(self):
        """
        With 2 products being picked from 1 pallet.
        Reserve stock for the picks.
        Picks should be merged, with a package level for each pallet on the picking.
        """
        # Put both apple and banana quants onto a mixed pallet
        mixed_pallet = self.create_package()
        self.apple_quant.package_id = mixed_pallet
        self.banana_quant.package_id = mixed_pallet

        # Use original picking for apple
        products_info_apple = [{"product": self.apple, "uom_qty": 10}]
        apple_move = self.create_move(self.picking, products_info_apple)

        # Create new picking for banana
        banana_picking = self.create_picking(self.picking_type_pick)
        products_info_banana = [{"product": self.banana, "uom_qty": 10}]
        banana_move = self.create_move(banana_picking, products_info_banana)

        # Reserve stock for apple picking then banana picking
        self.picking.action_assign()
        banana_picking.action_assign()
        # Banana picking should be merged into apple picking
        self.assertTrue(self.picking.exists())
        self.assertFalse(banana_picking.exists())
        self.assertFalse(self.picking.date_done)
        self.assertEqual(apple_move | banana_move, self.picking.move_lines)

        # Should be a single package level linked to both apple and banana move line
        self._assert_package_levels(self.picking)

    def test_2_pallets_over_backorder_preserves_package_levels_in_picking_chain(self):
        """
        With 1 product being picked onto two pallets via a backorder.
        Reserve and complete both the original pick and the backorder. Then process next picking.
        The package levels for each pallet should be properly set on the picking containing
        each pallet.
        """
        # Clear out refactoring rules on Pick, apply to Goods Out
        self.picking_type_pick.u_post_assign_action = False
        self.picking_type_goods_out.write(
            {
                "u_post_assign_action": "group_by_move_line_key",
                "u_move_line_key_format": "{package_id.name}",
            }
        )

        # Remove pallet from apple quant, apple will be picked loose onto a pallet
        self.apple_quant.package_id = False

        products_info = [{"product": self.apple, "uom_qty": 10}]
        self.create_move(self.picking, products_info)
        self.picking.action_assign()

        # Pick 7 of the 10 apples onto Pallet 1
        pallet1 = self.create_package()
        # Goods out picking should not have any package levels yet
        self._assert_package_levels(self.picking.u_next_picking_ids)
        self.picking.move_line_ids.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "result_package_id": pallet1.id,
                "qty_done": 7,
            }
        )
        self.picking._action_done()
        # Pick partially completed on Pallet 1, goods out picking should have a package level
        self._assert_package_levels(self.picking.u_next_picking_ids)

        # Pick remaining 3 apples onto Pallet 2
        backorder = self.picking.backorder_ids
        pallet2 = self.create_package()
        backorder.move_line_ids.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "result_package_id": pallet2.id,
                "qty_done": 3,
            }
        )
        backorder._action_done()

        # Goods out picking should be split out into two pickings, one for each pallet
        pick_pickings = self.picking | backorder
        goods_out_pickings = pick_pickings.u_next_picking_ids
        self.assertEqual(len(goods_out_pickings), 2)
        self.assertEqual(len(goods_out_pickings.move_lines), 2)
        # Verify that each picking has the correct package level for its pallet
        self._assert_package_levels(goods_out_pickings)


        # Complete each goods out picking and ensure after each one that the
        # package levels are still correct
        for picking in goods_out_pickings:
            self.assertFalse(picking.date_done)
            picking_ml = picking.move_line_ids
            picking_ml.write(
                {
                    "location_dest_id": self.test_trailer_location_01.id,
                    "result_package_id": picking_ml.package_id.id,
                    "qty_done": picking_ml.product_uom_qty,
                }
            )
            picking._action_done()
            self._assert_package_levels(goods_out_pickings)
            self.assertTrue(picking.date_done)

    def test_refactors_partially_unavailable_stock_into_new_move(self):
        """The system should split moves into available and unavailable."""
        products_info = [
            {"product": self.apple, "uom_qty": 15},
        ]
        original_move = self.create_move(self.picking, products_info)

        self.picking.action_assign()

        apple_move_lines = self.get_move_lines_for_product(
            self.apple, picking_type=self.picking_type_pick
        )
        refactored_moves = apple_move_lines.move_id

        self._assert_move_fields(original_move, self.apple, 5)
        self._assert_move_fields(refactored_moves, self.apple, 10)

        self._assert_move_line_fields(apple_move_lines, self.apple, 10, self.apple_pallet)

        self._assert_picking_fields(self.picking, state="confirmed")
        self._assert_picking_fields(refactored_moves.picking_id, state="assigned")
        self.assertFalse(refactored_moves.picking_id.date_done)


class TestValidateRefactoring(TestRefactoringBase):
    def setUp(self):
        """
        Set post validate action for test pick type
        """
        # group by destination location post validation
        self.picking_type_pick.write(
            {
                "u_post_validate_action": "group_by_move_line_key",
                "u_move_line_key_format": "{location_dest_id.name}",
            }
        )

        super(TestValidateRefactoring, self).setUp()

    def test_validate_2_locations_splits_2_picks(self):
        """
        With 2 different locations.
        Reserve (action_assign) and validate pick (_action_done).
        Pick should be split into 2 picks, one per location.
        """
        products_info = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 10},
        ]
        moves = self.create_move(self.picking, products_info)
        self.assertEqual(len(moves), 2)
        apple_move = moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = moves - apple_move
        self.picking.action_assign()
        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids
        apple_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "qty_done": apple_move_line.product_uom_qty,
            }
        )
        banana_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_02.id,
                "qty_done": banana_move_line.product_uom_qty,
            }
        )

        self.assertEqual(apple_move_line.picking_id, self.picking)
        self.assertEqual(banana_move_line.picking_id, self.picking)
        self.assertFalse(self.picking.date_done)
        self.picking._action_done()
        self.assertTrue(self.picking.date_done)
        # Check that apple and banana moves are now in different picks
        # and the original pick has been reused.
        self.assertNotEqual(apple_move.picking_id, banana_move.picking_id)
        self.assertTrue(
            self.picking == apple_move.picking_id or self.picking == banana_move.picking_id
        )

    def test_validate_2_locations_assert_new_pick_extra_info_maintained(self):
        """
        With 2 different locations.
        Reserve (action_assign) and validate pick (_action_done).
        Pick should be split into 2 picks, one per location.
        Extra info should be copied to new pick.

        Extra info:
            - origin
            - partner_id
            - date_done (comes from move.date when not reusing pick)
        """
        products_info = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 10},
        ]
        moves = self.create_move(self.picking, products_info)
        self.assertEqual(len(moves), 2)
        apple_move = moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = moves - apple_move
        self.picking.action_assign()
        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids
        apple_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "qty_done": apple_move_line.product_uom_qty,
            }
        )
        banana_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_02.id,
                "qty_done": banana_move_line.product_uom_qty,
            }
        )
        # Prepare pick extra info to keep
        partner = self.create_partner("Test Partner 123")
        origin = "Test origin 123"
        self.picking.write({"origin": origin, "partner_id": partner.id})
        self.assertFalse(self.picking.date_done)
        self.picking._action_done()
        self.assertTrue(self.picking.date_done)
        # apple and banana moves are now in different picks
        # and the original pick has been reused.
        self.assertNotEqual(apple_move.picking_id, banana_move.picking_id)
        self.assertTrue(
            self.picking == apple_move.picking_id or self.picking == banana_move.picking_id
        )
        # Check the pick extra info
        self._assert_picking_fields(apple_move.picking_id, origin=origin, partner=partner)
        self._assert_picking_fields(banana_move.picking_id, origin=origin, partner=partner)
        # Date done of the pick is the date of the moves
        # unless it's been reused
        if self.picking == apple_move.picking_id:
            self.assertGreaterEqual(apple_move.picking_id.date_done, apple_move.date)
            self.assertEqual(banana_move.picking_id.date_done, banana_move.date)
        else:
            self.assertEqual(apple_move.picking_id.date_done, apple_move.date)
            self.assertGreaterEqual(banana_move.picking_id.date_done, banana_move.date)

    def test_validate_2_picks_assert_new_pick_extra_info_maintained(self):
        """
        With 2 different picks each with 2 different locations
        (1 of each location per pick).
        Reserve (action_assign) and validate picks (_action_done).
        Picks should be maintained by with each pick now having
        two moves of the same location.
        Extra info should be copied to new pick.

        Extra info:
            - origin
            - partner_id
            - date_done (comes from move.date)
        """
        # Setup pick 1
        pick1_products_info = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 10},
        ]
        pick1_moves = self.create_move(self.picking, pick1_products_info)
        self.assertEqual(len(pick1_moves), 2)
        apple_move = pick1_moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = pick1_moves - apple_move
        self.picking.action_assign()
        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids
        apple_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "qty_done": apple_move_line.product_uom_qty,
            }
        )
        banana_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_02.id,
                "qty_done": banana_move_line.product_uom_qty,
            }
        )
        # Setup pick 2
        self.picking_2 = self.create_picking(self.picking_type_pick)
        cherry_pallet = self.create_package()
        self.create_quant(
            self.cherry.id, self.test_stock_location_01.id, 10, package_id=cherry_pallet.id
        )
        damson_pallet = self.create_package()
        self.create_quant(
            self.damson.id, self.test_stock_location_01.id, 10, package_id=damson_pallet.id
        )
        pick2_products_info = [
            {"product": self.cherry, "uom_qty": 10},
            {"product": self.damson, "uom_qty": 10},
        ]
        pick2_moves = self.create_move(self.picking_2, pick2_products_info)
        self.assertEqual(len(pick2_moves), 2)
        cherry_move = pick2_moves.filtered(lambda m: m.product_id == self.cherry)
        damson_move = pick2_moves - cherry_move
        self.picking_2.action_assign()
        cherry_move_line = cherry_move.move_line_ids
        damson_move_line = damson_move.move_line_ids
        cherry_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "qty_done": cherry_move_line.product_uom_qty,
            }
        )
        damson_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_02.id,
                "qty_done": damson_move_line.product_uom_qty,
            }
        )

        # Prepare both picks extra info and validate them at the same time
        both_picks = self.picking | self.picking_2
        self.assertFalse(self.picking.date_done)
        self.assertFalse(self.picking_2.date_done)
        partner = self.create_partner("Test Partner 123")
        origin = "Test origin 123"
        priority = "1"
        both_picks.write({"origin": origin, "partner_id": partner.id, "priority": priority})
        both_picks._action_done()
        # apple and banana moves are now in different picks.
        self.assertEqual(
            len(self.picking | apple_move.picking_id | banana_move.picking_id),
            3,
        )
        self.assertEqual(apple_move.picking_id, cherry_move.picking_id)
        self.assertEqual(banana_move.picking_id, damson_move.picking_id)
        # Check pick extra info and date done of the pick is the date of the move
        self._assert_picking_fields(
            apple_move.picking_id,
            origin=origin,
            partner=partner,
            date_done=apple_move.date,
            priority=priority,
        )
        self._assert_picking_fields(
            banana_move.picking_id,
            origin=origin,
            partner=partner,
            date_done=banana_move.date,
            priority=priority,
        )


class TestConfirmRefactoring(TestRefactoringBase):
    def setUp(self):
        """
        Set post confirm action for test pick type
        """
        # group by package post confirm
        self.picking_type_pick.write(
            {
                "u_post_confirm_action": "group_by_move_key",
                "u_move_key_format": "{product_id.default_code}",
            }
        )

        super(TestConfirmRefactoring, self).setUp()

    def test_confirm_2_prods_assert_split_1_pick_per_prod(self):
        """
        With 2 different products.
        Confirm (action_confirm) pick.
        Pick should be split into 2 picks 1 for each pallet,
        reusing the original pick.
        """
        products_info = [
            {"product": self.apple, "uom_qty": 5},
            {"product": self.banana, "uom_qty": 10},
        ]
        moves = self.create_move(self.picking, products_info)
        self.assertEqual(len(moves), 2)
        apple_move = moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = moves - apple_move
        self.picking.action_confirm()
        apple_pick = apple_move.picking_id
        banana_pick = banana_move.picking_id

        # apple and banana moves are now in different picks
        # and the original pick has been reused.
        self.assertNotEqual(apple_pick, banana_pick)
        self.assertTrue(self.picking == apple_pick or self.picking == banana_pick)
        self.assertEqual(apple_pick.move_lines, apple_move)
        self.assertEqual(banana_pick.move_lines, banana_move)
        self.assertFalse(apple_pick.date_done)
        self.assertFalse(banana_pick.date_done)
        self._assert_picking_fields(apple_pick, state="confirmed")
        self._assert_picking_fields(banana_pick, state="confirmed")

    def test_disable_move_refactor_context(self):
        """If refactor is called with context disable_move_refactor set to True,
        it should not refactor even if the refactoring criteria are met"""

        products_info = [
            {"product": self.apple, "uom_qty": 5},
            {"product": self.banana, "uom_qty": 10},
        ]
        moves = self.create_move(self.picking, products_info)
        self.assertEqual(len(moves), 2)
        apple_move = moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = moves - apple_move
        apple_pick = apple_move.picking_id
        banana_pick = banana_move.picking_id
        self.picking.with_context(disable_move_refactor=True).action_confirm()
        # On the test before test_confirm_2_prods_assert_split_1_pick_per_prod we tested that
        # moves after confirm were in different pickings Because of disable_move_refactor they
        # will be on same picking now.
        self.assertTrue(self.picking == apple_pick)
        self.assertTrue(self.picking == banana_pick)
        self._assert_picking_fields(apple_pick, state="confirmed")
        self._assert_picking_fields(banana_pick, state="confirmed")
        self.assertFalse(self.picking.date_done)


class TestByDate(TestRefactoringBase):
    """Tests for grouping by date."""
    
    def setUp(self):
        """
        Set post confirm action for test pick type
        """
        Picking = self.env["stock.picking"]

        # group by package post confirm
        self.picking_type_pick.write(
            {
                "u_post_confirm_action": "batch_pickings_by_date",
            }
        )
        self.today = "2023-04-13"
        self.tomorrow = "2023-04-14"

        picks = [
            # Orders today.
            (self.today, 1),
            (self.today, 2),
            # Orders tomorrow.
            (self.tomorrow, 1),
            (self.tomorrow, 2),
        ]
        random.seed(42)
        random.shuffle(picks)
        self.picks_by_key = {
            (date, sequence): self.create_picking(
                name="{}/{}".format(date, sequence),
                picking_type=self.picking_type_pick,
                sequence=sequence,
                products_info=[
                    # Set the date here because create_picking creates the picking
                    # without moves then adds the moves, overwriting the `scheduled_date`.
                    dict(product=product, qty=1, expected_date=date)
                    for product in [self.apple, self.banana]
                ],
            )
            for date, sequence in picks
        }

        self.picks = Picking.union(*(self.picks_by_key.values()))
        for pick in self.picks:
            pick.with_context(disable_move_refactor=True).action_confirm()

        super(TestByDate, self).setUp()

    def test_refactor_by_date_returns_moves(self):
        """Verify that refactoring by date returns same moves."""
        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        batches_before_refactoring = picks.batch_id
        self.assertEqual(len(batches_before_refactoring), 0)
        # It returns the moves sent to refactor
        refactored_moves = picks.move_lines._action_refactor()
        self.assertEqual(refactored_moves, picks.move_lines)
        batches_after_refactoring = picks.batch_id
        self.assertEqual(len(batches_after_refactoring), 2)


class TestRefactoringAssignSplittingQuantity(TestRefactoringBase):
    """Tests splitting by maximum quantity."""

    def setUp(self):
        """
        Split picking to maximum quantity
        """
        self.picking_type_pick.write(
            {
                "u_post_assign_action": "by_maximum_quantity",
                "u_assign_refactor_constraint_value": 2,
            }
        )
        self.picking = self.create_picking(self.picking_type_pick)

    def test_split_equally(self):
        """Check that a pick is split according to maximum quantity"""
        Picking = self.env["stock.picking"]

        # Create apple quant
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 10)
        products_info = [{"product": self.apple, "uom_qty": 10}]
        self.create_move(self.picking, products_info)
        self.picking.origin = "0001"
        self.picking.action_assign()

        # Get pickings
        all_pickings = Picking.search([
            ("picking_type_id", "=", self.picking_type_pick.id),
            ("origin", "=", "0001")
        ])
        # Check each picking is only for 2 products
        self.assertEqual(len(all_pickings), 5)
        self.assertTrue(
            all([sum(pick.move_lines.mapped("product_uom_qty")) == 2 for pick in all_pickings])
        )

    def test_split_unequally(self):
        """Check that a pick is split according to maximum quantity
        when it doesn't divide equally
        """
        Picking = self.env["stock.picking"]

        # Create apple quant
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 7)
        products_info = [{"product": self.apple, "uom_qty": 7}]
        self.create_move(self.picking, products_info)
        self.picking.origin = "0002"
        self.picking.action_assign()

        # Get pickings
        all_pickings = Picking.search([
            ("picking_type_id", "=", self.picking_type_pick.id),
            ("origin", "=", "0002")
        ])
        # Check pickings are split correctly
        self.assertEqual(len(all_pickings), 4)
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [2, 2, 2, 1])

    def test_split_partial_reserve(self):
        """Check that a pick is split according to maximum quantity
        with any unreserved quantities moved to a separate picking
        """
        Picking = self.env["stock.picking"]

        # Create apple quant
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 7)
        products_info = [{"product": self.apple, "uom_qty": 10}]
        self.create_move(self.picking, products_info)
        self.picking.origin = "0003"
        self.picking.action_assign()

        # Get pickings
        all_pickings = Picking.search([
            ("picking_type_id", "=", self.picking_type_pick.id),
            ("origin", "=", "0003")
        ])
        # Check pickings are split correctly
        self.assertEqual(len(all_pickings), 5)
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(2, 2), (2, 2), (2, 2), (1, 1), (3, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        # Check that there is only one picking which is not reserved
        unreserved_picking = all_pickings.filtered(lambda p: p.state == "confirmed")
        self.assertEqual(len(unreserved_picking), 1)

    def test_split_mixed_products(self):
        """Check that using multiple products still splits by quantity"""
        Picking = self.env["stock.picking"]

        # Create quants
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 5)
        apples_info = [{"product": self.apple, "uom_qty": 5}]
        bananas_info = [{"product": self.banana, "uom_qty": 5}]
        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.origin = "0004"
        self.picking.action_assign()

        # Get pickings
        all_pickings = Picking.search([
            ("picking_type_id", "=", self.picking_type_pick.id),
            ("origin", "=", "0004")
        ])
        # Check each picking is only for 2 products
        self.assertEqual(len(all_pickings), 5)
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(2, 2), (2, 2), (2, 2), (2, 2), (2, 2)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        # Check that one picking is for 1 banana and 1 apple
        mixed_picking = all_pickings.filtered(lambda p: len(p.move_lines) == 2)
        self.assertEqual(len(mixed_picking), 1)
        self.assertCountEqual(
            mixed_picking.move_lines.mapped("product_id").ids, (self.apple + self.banana).ids
        )
        self.assertEqual(mixed_picking.move_lines.mapped("product_uom_qty"), [1, 1])

    def test_split_mixed_products_partial_reserve(self):
        """Check that using multiple products still splits by quantity
        with any unreserved quantities moved to a seprate picking
        """
        Picking = self.env["stock.picking"]

        # Create quants
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 5)
        apples_info = [{"product": self.apple, "uom_qty": 7}]
        bananas_info = [{"product": self.banana, "uom_qty": 8}]
        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.origin = "0005"
        self.picking.action_assign()

        # Get pickings
        all_pickings = Picking.search([
            ("picking_type_id", "=", self.picking_type_pick.id),
            ("origin", "=", "0005")
        ])
        # Check each picking has a maximum quantity of 2
        self.assertEqual(len(all_pickings), 6)
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(2, 2), (2, 2), (2, 2), (2, 2), (2, 2), (5, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        # Check that there is one picking which is not reserved and the stock that is not
        # reserved is as expected
        unreserved_picking = all_pickings.filtered(lambda p: p.state == "confirmed")
        self.assertEqual(len(unreserved_picking), 1)
        moves = unreserved_picking.move_lines
        self.assertEqual(len(moves), 2)
        move_format = [(m.product_id, m.product_uom_qty, m.reserved_availability) for m in moves]
        expected_move_format = [(self.apple, 2, 0), (self.banana, 3, 0)]
        self.assertCountEqual(move_format, expected_move_format)
