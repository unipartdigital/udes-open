# -*- coding: utf-8 -*-

from odoo.addons.udes_stock.tests import common


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
    ):
        """
        Assert that the supplied picking recordset has only 1 record.
        Assert that the state, origin, partner, group name, location,
        destination location and date done match the expected values 
        if supplied.
        """
        self.assertEqual(len(picking), 1)

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

        products_info = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
        moves = self.create_move(self.picking, products_info)

        apple_move = moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = moves - apple_move

        self.picking.action_assign()

        apple_pick = apple_move.picking_id
        banana_pick = banana_move.picking_id

        # Assert picking fields are correct. Different group names ensure
        # apple_pick and banana_pick are not the same.
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
        MoveLine = self.env["stock.move.line"]

        apple_pallet = self.apple_pallet

        other_apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=other_apple_pallet.id
        )

        products_info = [{"product": self.apple, "qty": 20}]
        self.create_move(self.picking, products_info)

        self.picking.action_assign()

        apple_move_lines = MoveLine.search([("product_id.name", "=", "Test product Apple")])
        self.assertEqual(len(apple_move_lines), 2)

        apple_pallet_move_line = apple_move_lines.filtered(lambda ml: ml.package_id == apple_pallet)
        other_apple_pallet_move_line = apple_move_lines - apple_pallet_move_line

        apple_pick = apple_pallet_move_line.picking_id
        other_apple_pick = other_apple_pallet_move_line.picking_id

        # Assert picking fields are correct. Different group names ensure
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

        # Check that the original pick has been reused
        self.assertTrue(self.picking.exists())

        original_picking_reused = self.picking in (apple_pick | other_apple_pick)
        self.assertTrue(original_picking_reused)

    def test_reserve_1_pallet_diff_prods_splits_1_pick(self):
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

        products_info = [{"product": fig, "qty": 5}, {"product": grape, "qty": 10}]
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

    def test_reserve_simultaneously_2_picks_1_pallet_same_prods_merges_1_pick(self):
        """
        With 2 picks for 2 of the same products on one pallet.
        Reserve both picks (action_assign) simultaneously.
        Original pick should be marked as empty and deleted.
        A new pick should be created with both the moves.
        """
        apple_pallet = self.apple_pallet

        self.apple_quant.quantity = 25

        pick1 = self.picking
        pick2 = self.create_picking(self.picking_type_pick)

        pick1_products_info = [{"product": self.apple, "qty": 10}]
        move1 = self.create_move(pick1, pick1_products_info)

        pick2_products_info = [{"product": self.apple, "qty": 15}]
        move2 = self.create_move(pick2, pick2_products_info)

        (pick1 | pick2).action_assign()

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

        # Check that neither pick has been reused, empty picks have been
        # marked (u_mark = False) and deleted at the very end of the action
        self.assertFalse(pick1.exists())
        self.assertFalse(pick2.exists())

    def test_reserve_sequentially_2_picks_1_pallet_same_prods_merges_1_pick(self):
        """
        With 2 picks for 2 of the same products on one pallet.
        Reserve both picks (action_assign) sequentially.
        Original pick should be marked as empty and deleted.
        A new pick should be created with both the moves.
        """
        apple_pallet = self.apple_pallet

        self.apple_quant.quantity = 25

        pick1 = self.picking
        pick2 = self.create_picking(self.picking_type_pick)

        pick1_products_info = [{"product": self.apple, "qty": 10}]
        move1 = self.create_move(pick1, pick1_products_info)

        pick2_products_info = [{"product": self.apple, "qty": 15}]
        move2 = self.create_move(pick2, pick2_products_info)

        pick1.action_assign()
        pick2.action_assign()

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

        # Check that the first pick has been reused and the second pick
        # has been marked as empty (u_mark = False) and deleted at the very end
        # of the action
        self.assertTrue(pick1.exists())
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

        products_info = [{"product": self.apple, "qty": 10}]
        apple_move = self.create_move(self.picking, products_info)

        self.picking.action_assign()

        apple_pick = apple_move.picking_id

        # Check pick reuse
        self.assertEqual(self.picking, apple_pick)

        # Check pick state, location and destination location
        self._assert_picking_fields(
            apple_pick,
            state="assigned",
            location_id=self.test_stock_location_01,
            location_dest_id=self.test_goodsout_location_01,
        )


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
        Reserve (action_assign) and validate pick (action_done).
        Pick should be split into 2 picks, one per location.
        """
        products_info = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
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

        self.picking.action_done()

        # Check that apple and banana moves are now in different picks
        # and the original pick has been reused.
        self.assertNotEqual(apple_move.picking_id, banana_move.picking_id)
        self.assertTrue(
            self.picking == apple_move.picking_id or self.picking == banana_move.picking_id
        )

    def test_validate_2_locations_assert_new_pick_extra_info_maintained(self):
        """
        With 2 different locations.
        Reserve (action_assign) and validate pick (action_done).
        Pick should be split into 2 picks, one per location.
        Extra info should be copied to new pick.

        Extra info:
            - origin
            - partner_id
            - date_done (comes from move.date when not reusing pick)
        """
        products_info = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
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

        self.picking.action_done()

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
        Reserve (action_assign) and validate picks (action_done).
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
            {"product": self.apple, "qty": 10},
            {"product": self.banana, "qty": 10},
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
            {"product": self.cherry, "qty": 10},
            {"product": self.damson, "qty": 10},
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

        partner = self.create_partner("Test Partner 123")
        origin = "Test origin 123"
        both_picks.write({"origin": origin, "partner_id": partner.id})
        both_picks.action_done()

        # apple and banana moves are now in different picks.
        self.assertEqual(
            len(self.picking | apple_move.picking_id | banana_move.picking_id), 3,
        )

        self.assertEqual(apple_move.picking_id, cherry_move.picking_id)
        self.assertEqual(banana_move.picking_id, damson_move.picking_id)

        # Check pick extra info and date done of the pick is the date of the move
        self._assert_picking_fields(
            apple_move.picking_id, origin=origin, partner=partner, date_done=apple_move.date
        )
        self._assert_picking_fields(
            banana_move.picking_id, origin=origin, partner=partner, date_done=banana_move.date
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
        products_info = [{"product": self.apple, "qty": 5}, {"product": self.banana, "qty": 10}]
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

        self._assert_picking_fields(apple_pick, state="confirmed")
        self._assert_picking_fields(banana_pick, state="confirmed")
