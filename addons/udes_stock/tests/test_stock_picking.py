import unittest
from unittest.mock import patch

from odoo.exceptions import ValidationError, UserError
from odoo.tools import mute_logger

from . import common


class TestStockPickingCommon(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPickingCommon, cls).setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.Location = cls.env["stock.location"]
        products_info = [{"product": cls.apple, "uom_qty": 10}]
        cls.test_picking_in = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=products_info,
            confirm=True,
            location_dest_id=cls.test_received_location_01.id,
        )
        cls.test_picking_pick = cls.create_picking(
            cls.picking_type_pick, products_info=products_info, confirm=True
        )

    def _get_expected_move_values(self, pick, product, uom_qty, uom_id=None, **kwargs):
        """Helper to get expected move values"""
        expected_move_values = {
            "product_id": product.id,
            "name": product.name,
            "product_uom": uom_id or product.uom_id.id,
            "product_uom_qty": uom_qty,
            "location_id": pick.location_id.id,
            "location_dest_id": pick.location_dest_id.id,
            "picking_id": pick.id,
            "priority": pick.priority,
            "picking_type_id": pick.picking_type_id.id,
            "description_picking": product.name,
        }
        expected_move_values.update(kwargs)
        return expected_move_values

    def _assert_picking_related_pickings_match_expected_values(self, pickings, expected_values):
        """
        Assert that each supplied picking returns the expected related picking records

        :args:
                - pickings: A recordset of pickings
                - expected_values: A dictionary with field names to check as keys
                                   Each value should be another dictionary with the picking as key,
                                   and expected pickings (or False for none) to return as value
        """
        for picking in pickings:
            # Loop through all fields that need to be checked
            for field in expected_values.keys():
                returned_picks = picking[field]
                expected_picks = expected_values[field][picking]

                if not expected_picks:
                    # Assert that the field returns an empty recordset
                    self.assertFalse(
                        returned_picks, f"{picking.name} should not have any pickings for '{field}'"
                    )
                else:
                    # Assert that the recordset only contains the expected picks
                    expected_pick_names = self.get_picking_names(expected_picks)

                    self.assertEqual(
                        returned_picks,
                        expected_picks,
                        f"'{field}' for {picking.name} should be '{expected_pick_names}'",
                    )


class TestStockPickingBackordering(TestStockPickingCommon):
    def test_picking_naming_convention(self):
        """
        Test that backorders get created with a -001 suffix,
        but non-backordered pickings are not.

        Create a picking and backorder twice to test it holds for chained
        pickings.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 100)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 50}],
            location_id=self.test_stock_location_02.id,
        )
        pick.move_lines[0].quantity_done = 10
        pick.move_line_ids.location_id = self.test_stock_location_01
        pick.move_line_ids.location_dest_id = self.test_goodsout_location_01
        pick._action_done()
        bk_picking_1 = pick.u_created_backorder_ids
        bk_picking_1.move_lines[0].quantity_done = 10
        bk_picking_1.move_line_ids.location_id = self.test_stock_location_01
        bk_picking_1.move_line_ids.location_dest_id = self.test_goodsout_location_01
        bk_picking_1._action_done()
        bk_picking_2 = bk_picking_1.u_created_backorder_ids

        # Check naming convention
        self.assertNotRegex("-", pick.name)
        self.assertEqual(bk_picking_1.name, pick.name + "-001")
        self.assertEqual(bk_picking_2.name, pick.name + "-002")

    @patch("odoo.addons.udes_stock.models.common.MAX_SEQUENCE", 9)
    def test_picking_naming_convention_exceeds_limit(self):
        """
        Test that when 10 backorders get created with a -\d suffix,
        we handle what happens when the maximum sequence threshold is exceeded.
        We have mocked the MAX_SEQUENCE variable to be 9, so significantly
        smaller than the default 1000.
        """
        Picking = self.env["stock.picking"]
        MAX_SEQUENCE = 9
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 11)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 11}],
            location_id=self.test_stock_location_02.id,
        )
        picking = pick
        for i in range(9):
            picking.move_lines[0].quantity_done = 1
            picking.move_line_ids.location_dest_id = self.test_goodsout_location_01
            picking._action_done()
            # Store the previous picking for later checks
            prev_picking = picking
            self.assertEqual(prev_picking.state, "done")
            # NOTE: Get the next picking by picking type and state, doing it via u_created_back_orders
            # hits a cache error after 240.
            picking = Picking.search(
                [("picking_type_id", "=", self.picking_type_pick.id), ("state", "=", "assigned")]
            )
            self.assertEqual(len(picking), 1)
            self.assertEqual(picking.backorder_id, prev_picking)

        # Check we are where we think
        self.assertEqual(picking.name, f"{pick.name}-9")

        # Check completing this picking raises an error due to the maximum number of backorders is exceeded
        picking.move_lines[0].quantity_done = 1
        picking.move_line_ids.location_dest_id = self.test_goodsout_location_01
        with self.assertRaises(UserError) as e, mute_logger("odoo.sql_db"):
            picking._action_done()

        # Check the error is as expected
        sequence = 10
        self.assertEqual(
            e.exception.args[0],
            """
            Trying to create a backorder with sequence %d
            but this exceeds the maximum allowed %d
            """
            % (sequence, MAX_SEQUENCE),
        )

    def test_backorders_are_named_in_order_of_creation(self):
        """
        Test that even if a picking tree is created, that the backorders are named
        accroding to the order they are created.

        Pick 001 - 6 moves (ignore the moves that is not the important bit!)

        We want to show the picking tree structure and the naming,
        the Ref column refers to the order a picking is created in.

        Ref        | Name       | Orignal | Parent | 1st Gen Children |
        Pick       | Pick001    | Pick001 |   -    | Pick1, Pick3     |
        Pick1      | Pick001-01 | Pick001 | Pick   | Pick2            |
        Pick2      | Pick001-02 | Pick001 | Pick1  |        -         |
        Pick3      | Pick001-03 | Pick001 | Pick   | Pick4, Pick5     |
        Pick4      | Pick001-04 | Pick001 | Pick3  |        -         |
        Pick5      | Pick001-05 | Pick001 | Pick3  |        -         |

                        Original Picking (Pick001)
                                |
            ----------------------------------------
            |                                       |
        pick1  (Pick001-001)                      pick 3  (Pick001-003)
            |                                       |
            |                           -------------------------
            |                           |                       |
        pick2  (Pick001-002)        pick4  (Pick001-004)        pick5  (Pick001-005)
        """
        pick = self.create_picking(
            picking_type=self.picking_type_goods_in,
            products_info=[
                {"product": self.apple, "uom_qty": 50},
                {"product": self.banana, "uom_qty": 50},
                {"product": self.cherry, "uom_qty": 50},
                {"product": self.damson, "uom_qty": 50},
                {"product": self.grape, "uom_qty": 50},
                {"product": self.fig, "uom_qty": 50},
            ],
            assign=True,
        )
        mls = pick.move_line_ids
        self.assertEqual(len(mls), 6)

        abcd_products = self.apple | self.banana | self.cherry | self.damson

        # Create a backorder from the original, then a backorder from that
        pick1 = pick.backorder_move_lines(
            mls_to_keep=mls.filtered(lambda mv: mv.product_id in abcd_products)
        )
        pick2 = pick1.backorder_move_lines(
            mls_to_keep=mls.filtered(lambda mv: mv.product_id == self.grape)
        )

        # Now create a backorder from the original, then two backorders from that
        pick3 = pick.backorder_move_lines(
            mls_to_keep=mls.filtered(lambda mv: mv.product_id == self.apple)
        )
        pick4 = pick3.backorder_move_lines(
            mls_to_keep=mls.filtered(lambda mv: mv.product_id in (self.cherry | self.banana))
        )
        pick5 = pick3.backorder_move_lines(
            mls_to_keep=mls.filtered(lambda mv: mv.product_id == self.banana)
        )

        # Check the state of the pickings
        pickings = pick | pick1 | pick2 | pick3 | pick4 | pick5
        for picking in pickings:
            with self.subTest(picking=picking.name):
                self.assertTrue(picking.move_line_ids)
                self.assertEqual(picking.state, "assigned")

        # Check naming convention
        self.assertNotRegex("-", pick.name)
        self.assertEqual(pick1.name, pick.name + "-001")
        self.assertEqual(pick2.name, pick.name + "-002")
        self.assertEqual(pick3.name, pick.name + "-003")
        self.assertEqual(pick4.name, pick.name + "-004")
        self.assertEqual(pick5.name, pick.name + "-005")

    def test_action_done_deletes_and_recreates_move_lines(self):
        """
        A unit test to keep track of `_action_done` behaviour. If the core behaviour
        changes this test should fail and need to be updated.
        Current expected behaviour is the moves remain, but the move lines get deleted
        and re-created when splitting.
        """
        Move = self.env["stock.move"]
        MoveLine = self.env["stock.move.line"]
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 50)
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.fig, "uom_qty": 20},
                {"product": self.fig, "uom_qty": 10},
            ],
        )
        banana_ml = pick.move_lines.filtered(lambda ml: ml.product_id == self.banana)
        fig_ml = pick.move_lines.filtered(lambda ml: ml.product_id == self.fig)
        banana_ml.quantity_done = 10
        fig_ml.quantity_done = 10
        pick.move_line_ids.location_id = self.test_stock_location_01
        pick.move_line_ids.location_dest_id = self.test_goodsout_location_01
        pick._action_done()
        moves = pick.move_lines

        # Assert the move lines are different
        self.assertNotEqual(pick.move_line_ids, banana_ml | fig_ml)
        old_mls = MoveLine.search([("id", "in", (banana_ml | fig_ml).ids)])
        self.assertFalse(old_mls)

        # Check the moves still exist for completeness
        old_moves = Move.search([("id", "in", moves.ids)])
        self.assertEqual(old_moves, moves)

    def test_check_backorder_allowed_raises_error_when_moving_cancelled_work(self):
        """Test that an eror is raised when cancelled moves are moved into a new backorder"""
        pick = self.create_picking(
            picking_type=self.picking_type_goods_in,
            products_info=[
                {"product": self.apple, "uom_qty": 50},
                {"product": self.fig, "uom_qty": 50},
            ],
            assign=True,
        )
        moves = pick.move_lines
        mls = pick.move_line_ids
        # Cancel the apple_mv
        apple_mv = moves.filtered(lambda mv: mv.product_id == self.apple)
        apple_ml = apple_mv.move_line_ids
        self.assertTrue(apple_mv)
        self.assertTrue(apple_ml)

        apple_mv._action_cancel()
        self.assertEqual(apple_mv.state, "cancel")

        # Try and move the cancelled move into a backorder
        with self.assertRaises(ValidationError) as e, mute_logger("odoo.sql_db"):
            pick._check_backorder_allowed(mls - apple_ml, apple_mv)

        # Check the error is as expected
        self.assertEqual(
            e.exception.args[0], "You cannot move completed or cancelled moves to a backorder!"
        )

    def test_check_backorder_allowed_raises_error_when_moving_done_work_and_leaving_incomplete_work(
        self,
    ):
        """Test that an eror is raised when scanned moves are moved into a new backorder,
        and the current picking has incomplete work.
        """
        pick = self.create_picking(
            picking_type=self.picking_type_goods_in,
            products_info=[
                {"product": self.apple, "uom_qty": 50},
                {"product": self.fig, "uom_qty": 50},
            ],
            assign=True,
        )
        moves = pick.move_lines
        mls = pick.move_line_ids
        # Scan the apple ml
        apple_mv = moves.filtered(lambda mv: mv.product_id == self.apple)
        apple_ml = apple_mv.move_line_ids
        apple_ml.qty_done = apple_ml.product_uom_qty

        # Try and move the cancelled move into a backorder
        with self.assertRaises(ValidationError) as e, mute_logger("odoo.sql_db"):
            pick._check_backorder_allowed(mls - apple_ml, apple_mv)

        # Check the error is as expected
        self.assertEqual(
            e.exception.args[0],
            "You cannot create a backorder for done move lines whilst retaining incomplete ones",
        )

    def test_backorder_move_lines_raises_exception_when_qty_done_in_ml_partially_complete(
        self,
    ):
        """
        When trying to create a backorder with a move line of qty_done < product_uom_qty an
        error is raised.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 50}],
            assign=True,
        )
        ml = pick.move_line_ids
        ml.qty_done = 10

        # Run the test with and without mls
        for move_line in [None, ml]:
            with self.subTest(pass_mls=bool(move_line)), self.assertRaises(
                ValidationError
            ) as e, mute_logger("odoo.sql_db"):
                pick._backorder_move_lines(mls_to_keep=move_line)

                # Check the error is as expected
                self.assertEqual(
                    e.exception.args[0],
                    "You cannot create a backorder with partially fulfilled move lines!",
                )

    def test_backorder_move_lines_returns_empty_record_when_mls_cover_moves_and_everything_done(
        self,
    ):
        """
        Test when we try to backorder all the mls, with qty_done that covers the move, an
        empty record set is returned.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 50}],
            assign=True,
        )
        ml = pick.move_line_ids
        ml.qty_done = ml.product_uom_qty
        for move_line in [ml, None]:
            with self.subTest(mls_passed=bool(move_line)):
                bk_pick = pick._backorder_move_lines(ml)
                self.assertFalse(bk_pick, pick)

    def test_backorder_move_lines_when_complete_and_incomplete_mls(self):
        """
        Create a backorder with the partially complete move lines.
        The fully complete, and partially done part of the banana move line
        should remain in the original picking, with the new picking having
        the remaining incomplete work.

        Scenario:
        Pick 1
            * apple: 10, qty_done = 10
            * banana: 20, qty_done = 0

        Then backorder Pick 1, we should expect
        Pick 1
            * apple: 10
        Pick 1-001
            * banana: 20
        """
        self.create_quant(self.apple.id, self.test_stock_location_02.id, 10)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 20)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 10},
                {"product": self.banana, "uom_qty": 20},
            ],
            assign=True,
        )
        self.assertEqual(pick.state, "assigned")

        # Get information to check later
        mls = pick.move_line_ids
        apple_ml = pick.move_line_ids.filtered(lambda ml: ml.product_id == self.apple)
        apple_mv = apple_ml.move_id
        banana_ml = mls - apple_ml
        banana_mv = banana_ml.move_id
        apple_ml.qty_done = apple_ml.product_uom_qty

        # Backorder move lines
        bk_picking = pick._backorder_move_lines()

        # Check the original picking and that the original move lines exist
        # and belong to the original picking.
        self.assertEqual(pick.state, "assigned")
        self.assertTrue(apple_ml)
        self.assertEqual(apple_mv, pick.move_lines)
        self.assertEqual(apple_ml, pick.move_line_ids)
        # Sanity check the move lines
        self.assertEqual(pick.move_line_ids.product_id, self.apple)
        self.assertEqual(pick.move_lines.product_qty, 10)
        self.assertEqual(pick.move_line_ids.qty_done, 10)

        # Check backorder picking
        self.assertEqual(bk_picking.backorder_id, pick)
        self.assertEqual(bk_picking.move_lines, banana_mv)
        self.assertEqual(bk_picking.move_line_ids, banana_ml)
        # Sanity check the move lines
        self.assertEqual(bk_picking.move_lines.product_qty, 20.0)
        self.assertEqual(bk_picking.move_line_ids.qty_done, 0.0)

        # Check the naming convention holds
        self.assertEqual(bk_picking.name, f"{pick.name}-001")

    def test_backorder_move_lines_propagates_partially_available_moves(self):
        """
        Check when we backorder a picking where the move lines are fully completed,
        but the move is not, the backorder gets created for the remainder of the move.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 5)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 20}],
            assign=True,
        )
        fig_mv = pick.move_lines
        fig_ml = pick.move_line_ids
        fig_ml.qty_done = 5

        # Check pick
        self.assertEqual(fig_ml.state, "partially_available")
        self.assertEqual(fig_ml.qty_done, 5)
        bk_picking = pick._backorder_move_lines()

        # Check original pick after backordering, the incomplete moves have been moved out
        # but the move line remains.
        self.assertEqual(pick.move_lines.state, "assigned")
        self.assertEqual(pick.move_lines, fig_mv)
        self.assertEqual(pick.move_lines.quantity_done, 5)
        self.assertEqual(pick.move_lines.product_uom_qty, 5)
        self.assertEqual(pick.move_line_ids, fig_ml)
        self.assertEqual(pick.move_line_ids.qty_done, 5)
        self.assertEqual(pick.move_line_ids.product_uom_qty, 5)

        # Check backorder pick
        self.assertEqual(pick, bk_picking.backorder_id)
        self.assertEqual(bk_picking.state, "confirmed")
        # No Move lines as nothing available yet
        self.assertFalse(bk_picking.move_line_ids)
        bk_move = bk_picking.move_lines
        self.assertEqual(bk_move.state, "confirmed")
        self.assertEqual(bk_move.quantity_done, 0)
        self.assertEqual(bk_move.product_uom_qty, 15)

    def test_backorder_move_lines_works_for_multiple_mls_single_mv(self):
        """
        Check when we backorder a picking which is partially available, all the unfullfilled
        move info gets propogated to the new backordered picking.

        Setup:
            Pick:
                * banana: 13, 7 reserved, 3 done

        Expect:
        Original Pick:
            * banana: 3, 3 reserved, 3 done
        Backorder Pick:
            * banana: 10, 4 reserved, 0 done
        """
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 3)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 4)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.banana, "uom_qty": 13}],
            assign=True,
        )
        move = pick.move_lines
        mls = pick.move_line_ids
        self.assertEqual(len(move), 1)
        self.assertEqual(len(mls), 2)
        # Fulfill one move line
        banana_3ml = mls.filtered(lambda ml: ml.product_uom_qty == 3)
        banana_3ml.qty_done = 3

        # Do backordering
        bk_picking = pick._backorder_move_lines()

        # Check original pick after backordering, the incomplete moves have been moved out
        updated_moves = pick.move_lines
        updated_mls = pick.move_line_ids
        self.assertEqual(updated_mls.state, "assigned")
        self.assertEqual(updated_moves, banana_3ml.move_id)
        self.assertEqual(updated_mls, banana_3ml)
        # Sanity check
        self.assertEqual(updated_moves.quantity_done, 3)
        self.assertEqual(updated_moves.product_uom_qty, 3)
        self.assertEqual(updated_mls.qty_done, 3)
        self.assertEqual(updated_mls.product_uom_qty, 3)

        # Check backorder pick
        self.assertEqual(pick, bk_picking.backorder_id)
        bk_moves = bk_picking.move_lines
        bk_mls = bk_picking.move_line_ids
        self.assertEqual(bk_moves.state, "partially_available")
        self.assertNotIn(move, bk_moves)
        self.assertEqual(bk_mls, mls - banana_3ml)
        self.assertEqual(bk_moves.quantity_done, 0)
        self.assertEqual(bk_moves.product_uom_qty, 10)
        self.assertEqual(bk_mls.qty_done, 0)
        self.assertEqual(bk_mls.product_uom_qty, 4)

    def test_backorder_move_lines_works_for_partially_fulfilled_and_available_moves(self):
        """
        Check when we backorder a picking with some moves fulfilled, partially fulfilled
        and not fulfilled, the backorder and original picking are as expected.

        Setup:
            Pick:
                * apple: 4, 4 reserved, 4 done
                * banana: 13, 7 reserved, 3 done
                * cherry: 8, 4 reserved, 0 done
                * damson: 2, 2 reserved, 0 done

        Expect:
        Original Pick:
            * apple: 4, 4 reserved, 4 done
            * banana: 3, 3 reserved, 3 done
        Backorder Pick:
            * banana: 10, 4 reserved, 0 done
            * cherry: 8, 4 reserved, 0 done
            * damson: 2, 2 reserved, 0 done
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 3)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 4)
        self.create_quant(self.cherry.id, self.test_stock_location_03.id, 4)
        self.create_quant(self.damson.id, self.test_stock_location_04.id, 2)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 4},
                {"product": self.banana, "uom_qty": 13},
                {"product": self.cherry, "uom_qty": 8},
                {"product": self.damson, "uom_qty": 2},
            ],
            assign=True,
        )
        moves = pick.move_lines
        mls = pick.move_line_ids
        self.assertEqual(len(moves), 4)
        self.assertEqual(len(mls), 5)

        # Fulfill the apple ml
        apple_mv = moves.filtered(lambda mv: mv.product_id == self.apple)
        apple_ml = apple_mv.move_line_ids
        apple_ml.qty_done = apple_ml.product_uom_qty

        # Fulfill one banana move line
        banana_mv = moves.filtered(lambda mv: mv.product_id == self.banana)
        banana_mls = banana_mv.move_line_ids
        banana_3ml = banana_mls.filtered(lambda ml: ml.product_uom_qty == 3)
        banana_4ml = banana_mls.filtered(lambda ml: ml.product_uom_qty == 4)
        banana_3ml.qty_done = banana_3ml.product_uom_qty

        # Do nothing with the cherries
        cherry_mv = moves.filtered(lambda mv: mv.product_id == self.cherry)
        cherry_ml = cherry_mv.move_line_ids

        # Do nothing with the damsons
        damson_mv = moves.filtered(lambda mv: mv.product_id == self.damson)
        damson_ml = damson_mv.move_line_ids

        # Do backordering
        bk_picking = pick._backorder_move_lines()

        # Check original pick after backordering, the incomplete moves have been moved out
        updated_moves = pick.move_lines
        updated_mls = pick.move_line_ids
        for ml in updated_mls:
            with self.subTest(product=ml.product_id.name):
                self.assertEqual(ml.state, "assigned")
        self.assertEqual(updated_moves, banana_mv | apple_mv)
        self.assertEqual(updated_mls, banana_3ml | apple_ml)
        # Sanity check
        self.assertCountEqual(updated_moves.mapped("quantity_done"), [3, 4])
        self.assertCountEqual(updated_moves.mapped("product_uom_qty"), [3, 4])
        self.assertCountEqual(updated_mls.mapped("qty_done"), [3, 4])
        self.assertCountEqual(updated_mls.mapped("product_uom_qty"), [3, 4])

        # Check backorder pick
        self.assertEqual(pick, bk_picking.backorder_id)
        bk_moves = bk_picking.move_lines
        bk_mls = bk_picking.move_line_ids
        self.assertIn(damson_mv, bk_moves)

        # Test only the damson move is in the backordered moves
        self.assertEqual(damson_mv | cherry_mv, bk_moves & moves)
        self.assertEqual(damson_mv.state, "assigned")

        # Test the new moves
        for move in bk_moves - damson_mv:
            with self.subTest(product=move.product_id.name):
                self.assertEqual(move.state, "partially_available")

        # The move lines should have been preserved
        self.assertEqual(bk_mls, cherry_ml | banana_4ml | damson_ml)
        # Sanity check
        self.assertEqual(sum(bk_moves.mapped("quantity_done")), 0)
        self.assertEqual(sum(bk_moves.mapped("product_uom_qty")), 20)
        self.assertEqual(sum(bk_mls.mapped("qty_done")), 0)
        self.assertEqual(sum(bk_mls.mapped("product_uom_qty")), 10)

    def test_backorder_move_lines_returns_empty_record_when_mls_cover_moves_and_nothing_done(self):
        """
        When trying to create a backorder via _backorder_move_lines, if the mls cover the move
        and the qty_done = 0, then it returns an empty record set.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 50}],
            assign=True,
        )
        ml = pick.move_line_ids
        bk_pick = pick._backorder_move_lines(ml)
        self.assertFalse(bk_pick)

    def test_backorder_move_lines_creates_backorder_when_mls_do_not_cover_moves(self):
        """
        When trying to create a backorder via _backorder_move_lines, if the mls do not
        cover the moves, then keep the mls in the original picking and place the rest
        into the backorder.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 100}],
            assign=True,
        )
        move = pick.move_lines
        ml = pick.move_line_ids
        bk_picking = pick._backorder_move_lines(ml)

        # Check the original picking just retains the available move line
        self.assertEqual(pick.move_lines, move)
        self.assertEqual(pick.move_lines.product_uom_qty, 50)
        self.assertEqual(pick.move_line_ids, ml)
        self.assertEqual(pick.move_line_ids.product_uom_qty, 50)

        # Check the backorder picking has the unavailable quantity
        self.assertTrue(bk_picking)
        self.assertEqual(bk_picking.state, "confirmed")
        self.assertEqual(bk_picking.move_lines.product_uom_qty, 50)
        self.assertFalse(bk_picking.move_line_ids)

    def test_backorder_move_lines_retains_all_mls_in_picking(self):
        """
        Check when we backorder a picking with a single move and multiple move
        lines, we can reatain a particular subset.

        Setup:
            Pick:
                * banana: 13, 7 reserved, 7 done

        Expect:
        Original Pick:
            * banana: 3, 3 reserved, 3 done
        Backorder Pick:
            * banana: 10, 4 reserved, 0 done
        """
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 3)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 4)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.banana, "uom_qty": 13}],
            assign=True,
        )
        moves = pick.move_lines
        mls = pick.move_line_ids
        self.assertEqual(len(moves), 1)
        self.assertEqual(len(mls), 2)

        # Fulfill both banana mls, retain the one with qty 3
        banana_mv = moves.filtered(lambda mv: mv.product_id == self.banana)
        banana_mls = banana_mv.move_line_ids
        banana_3ml = banana_mls.filtered(lambda ml: ml.product_uom_qty == 3)
        banana_4ml = banana_mls.filtered(lambda ml: ml.product_uom_qty == 4)
        banana_3ml.qty_done = banana_3ml.product_uom_qty
        banana_4ml.qty_done = banana_4ml.product_uom_qty

        # Do backordering
        bk_picking = pick._backorder_move_lines(banana_3ml)

        # Check original pick after backordering, the incomplete moves have been moved out
        updated_move = pick.move_lines
        updated_ml = pick.move_line_ids
        self.assertEqual(updated_ml.state, "assigned")
        self.assertEqual(updated_move, banana_mv)
        self.assertEqual(updated_ml, banana_3ml)
        # Sanity check
        self.assertEqual(updated_move.quantity_done, 3)
        self.assertEqual(updated_move.product_uom_qty, 3)
        self.assertEqual(updated_ml.qty_done, 3)
        self.assertEqual(updated_ml.product_uom_qty, 3)

        # Check backorder pick
        self.assertEqual(pick, bk_picking.backorder_id)
        bk_move = bk_picking.move_lines
        bk_ml = bk_picking.move_line_ids
        self.assertNotIn(banana_mv, bk_move)
        self.assertEqual(banana_4ml, bk_ml)
        self.assertEqual(bk_move.state, "partially_available")

        # Sanity check
        self.assertEqual(bk_move.quantity_done, 4)
        self.assertEqual(bk_move.product_uom_qty, 10)
        self.assertEqual(bk_ml.qty_done, 4)
        self.assertEqual(bk_ml.product_uom_qty, 4)

    def test_backorder_move_lines_raises_error_when_retained_mls_not_done_but_others_are(self):
        """
        Check when we backorder a picking trying to retain mls not yet complete, it raises an
        error if other mls are.
        """
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 3)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 4)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.banana, "uom_qty": 13}],
            assign=True,
        )
        moves = pick.move_lines
        mls = pick.move_line_ids
        self.assertEqual(len(moves), 1)
        self.assertEqual(len(mls), 2)

        # Fulfill the one with qty 4
        banana_3ml = mls.filtered(lambda ml: ml.product_uom_qty == 3)
        banana_4ml = mls - banana_3ml
        banana_4ml.qty_done = banana_4ml.product_uom_qty

        # Do backordering
        with self.assertRaises(ValidationError) as e, mute_logger("odoo.sql_db"):
            pick._backorder_move_lines(banana_3ml)

        # Check the error is as expected
        self.assertEqual(
            e.exception.args[0],
            "You cannot create a backorder for done move lines whilst retaining incomplete ones",
        )

    def test_backorder_move_lines_moves_all_move_quantity_when_not_fully_avialable(self):
        """
        Check when we backorder a picking with some moves fulfilled, partially fulfilled
        and not fulfilled, the backorder and original picking are as expected.

        Setup:
            Pick:
                * apple: 4, 4 reserved, 4 done
                * banana: 13, 7 reserved, 7 done
                * cherry: 8, 4 reserved, 4 done
                * damson: 2, 2 reserved, 0 done

        Retain only the 3ml for banana and cherry ml.
        Expect:
        Original Pick:
            * banana: 3, 3 reserved, 3 done
            * cherry: 4, 4 reserved, 4 done
        Backorder Pick:
            * apple: 4, 4 reserved, 4 done
            * banana: 10, 4 reserved, 0 done
            * cherry: 4, 0 reserved, 0 done
            * damson: 2, 2 reserved, 0 done
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 3)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 4)
        self.create_quant(self.cherry.id, self.test_stock_location_03.id, 4)
        self.create_quant(self.damson.id, self.test_stock_location_04.id, 2)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 4},
                {"product": self.banana, "uom_qty": 13},
                {"product": self.cherry, "uom_qty": 8},
                {"product": self.damson, "uom_qty": 2},
            ],
            assign=True,
        )
        moves = pick.move_lines
        mls = pick.move_line_ids
        self.assertEqual(len(moves), 4)
        self.assertEqual(len(mls), 5)

        # Fulfill the apple ml
        apple_mv = moves.filtered(lambda mv: mv.product_id == self.apple)
        apple_ml = apple_mv.move_line_ids
        apple_ml.qty_done = apple_ml.product_uom_qty

        # Fulfill one banana move line
        banana_mv = moves.filtered(lambda mv: mv.product_id == self.banana)
        banana_mls = banana_mv.move_line_ids
        banana_3ml = banana_mls.filtered(lambda ml: ml.product_uom_qty == 3)
        banana_4ml = banana_mls.filtered(lambda ml: ml.product_uom_qty == 4)
        banana_3ml.qty_done = banana_3ml.product_uom_qty

        # Fulfill the cherry ml
        cherry_mv = moves.filtered(lambda mv: mv.product_id == self.cherry)
        cherry_ml = cherry_mv.move_line_ids
        cherry_ml.qty_done = cherry_ml.product_uom_qty

        # Do nothing with the damsons
        damson_mv = moves.filtered(lambda mv: mv.product_id == self.damson)
        damson_ml = damson_mv.move_line_ids

        # Do backordering
        bk_picking = pick._backorder_move_lines(cherry_ml | banana_3ml)

        # Check original pick after backordering, the incomplete moves have been moved out
        updated_moves = pick.move_lines
        updated_mls = pick.move_line_ids
        for ml in updated_mls:
            with self.subTest(product=ml.product_id.name):
                self.assertEqual(ml.state, "assigned")
        self.assertEqual(updated_moves, banana_mv | cherry_mv)
        self.assertEqual(updated_mls, banana_3ml | cherry_ml)
        # Sanity check
        self.assertCountEqual(updated_moves.mapped("quantity_done"), [3, 4])
        self.assertCountEqual(updated_moves.mapped("product_uom_qty"), [3, 4])
        self.assertCountEqual(updated_mls.mapped("qty_done"), [3, 4])
        self.assertCountEqual(updated_mls.mapped("product_uom_qty"), [3, 4])

        # Check backorder pick
        self.assertEqual(pick, bk_picking.backorder_id)
        bk_moves = bk_picking.move_lines
        bk_mls = bk_picking.move_line_ids
        self.assertIn(damson_mv, bk_moves)

        # Test only the damson move is in the backordered moves
        self.assertEqual(damson_mv | apple_mv, bk_moves & moves)
        self.assertEqual(apple_mv.state, "assigned")
        self.assertEqual(damson_mv.state, "assigned")
        self.assertEqual(
            bk_moves.filtered(lambda mv: mv.product_id == self.banana).state, "partially_available"
        )
        self.assertEqual(
            bk_moves.filtered(lambda mv: mv.product_id == self.cherry).state, "confirmed"
        )

        # The move lines should have been preserved
        self.assertEqual(bk_mls, apple_ml | banana_4ml | damson_ml)
        # Sanity check
        self.assertEqual(sum(bk_moves.mapped("quantity_done")), 4)
        self.assertEqual(sum(bk_moves.mapped("product_uom_qty")), 20)
        self.assertEqual(sum(bk_mls.mapped("qty_done")), 4)
        self.assertEqual(sum(bk_mls.mapped("product_uom_qty")), 10)

    def test_u_original_picking_id_gets_set_on_picking(self):
        """
        Test that u_original_picking_id gets set to the original picking on a chain of backorders
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 100}],
            assign=True,
        )
        move = pick.move_lines
        ml = pick.move_line_ids
        bk_picking = pick._backorder_move_lines(ml)
        bk_ml = bk_picking.move_line_ids
        bk_2_picking = bk_picking._backorder_move_lines(bk_ml)

        self.assertEqual(pick.u_original_picking_id, pick)
        self.assertEqual(bk_picking.u_original_picking_id, pick)
        self.assertEqual(bk_2_picking.u_original_picking_id, pick)

    def test_quantity_does_not_revert_on_cancelled_backorder(self):
        """
        Test that product_qty does not revert to u_uom_initial_demand when cancelling a picking
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 100}],
            assign=True,
        )
        ml = pick.move_line_ids
        bk_picking = pick._backorder_move_lines(ml)
        bk_move = bk_picking.move_lines
        self.assertEqual(bk_move.u_uom_initial_demand, 100)
        self.assertEqual(bk_move.product_qty, 50)
        bk_picking.action_cancel()
        self.assertEqual(bk_move.u_uom_initial_demand, 100)
        self.assertEqual(bk_move.product_qty, 50)

    def test_backorder_does_not_dangle_with_split_package(self):
        """If we start with a Pick for 50x figs, and pick it onto 2 separate packages
        ensure that no spurious backorder gets created"""
        StockPicking = self.env["stock.picking"]

        # Cancel existing picking so it doesn't interfere with new test
        self.test_picking_pick.action_cancel()

        pack1 = self.create_package(name="UDES01")
        pack2 = self.create_package(name="UDES02")
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 30, package_id=pack1.id)
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 20, package_id=pack2.id)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 50}],
            assign=True,
        )
        starting_picks = StockPicking.search([])
        for line in pick.move_line_ids:
            line.location_dest_id = self.test_goodsout_location_01
            line.qty_done = line.product_uom_qty
        pick.validate_picking()
        goods_out = pick.u_next_picking_ids
        for line in goods_out.move_line_ids:
            line.qty_done = line.product_uom_qty
            line.location_dest_id = self.test_trailer_location_01
        goods_out.validate_picking()
        ending_picks = StockPicking.search([])
        new_pick = ending_picks - starting_picks
        self.assertEqual(len(new_pick), 0)


class TestStockPicking(TestStockPickingCommon):
    def test_get_empty_locations(self):
        """Get empty locations - for goods in"""
        self.assertEqual(self.test_picking_in.get_empty_locations(), self.test_received_location_01)
        # Add stock to a location - to check empty locations obtained
        self.create_quant(self.apple.id, self.test_received_location_01.id, 5)
        self.assertFalse(self.test_picking_in.get_empty_locations())

    def test_get_empty_locations_sorted(self):
        """Empty locations are sorted when `sort` is set to True, otherwise not"""
        # Create location 'A' in zone 'Z'
        # When sorted by location name directly 'A' will appear first,
        # but in default location ordering it will be last
        zone_z = self.create_location(
            name="Zone Z", location_id=self.received_location.id, usage="view"
        )
        loc_a = self.create_location(name="A", barcode="LRTESTA", location_id=zone_z.id)

        # Set destination location of the test Goods In picking to the received zone
        self.test_picking_in.location_dest_id = self.received_location

        # Empty locations sorted by name, 'A' appears first
        self.assertEqual(self.test_picking_in.get_empty_locations(sort=True)[0], loc_a)

        # Empty locations not sorted, 'A' appears last
        self.assertEqual(self.test_picking_in.get_empty_locations(sort=False)[-1], loc_a)

    def test_get_empty_locations_limited(self):
        """Empty locations are limited when `limit` is set, otherwise not"""
        # Set destination location of the test Goods In picking to the received zone
        self.test_picking_in.location_dest_id = self.received_location

        # Empty locations not limited by default
        self.assertGreater(len(self.test_picking_in.get_empty_locations(limit=None)), 1)

        # Only one empty location is returned
        self.assertEqual(len(self.test_picking_in.get_empty_locations(limit=1)), 1)

    def test_get_child_locations_simple_success(self):
        """Get child locations"""
        self.assertEqual(
            self.test_picking_pick._get_child_dest_locations(), self.test_check_locations
        )

    def test_get_child_locations_simple_success_with_extra_domain(self):
        """Get child locations - with extra domain"""
        aux_domain = [("name", "=", self.test_check_location_01.name)]
        self.assertEqual(
            self.test_picking_pick._get_child_dest_locations(aux_domain=aux_domain),
            self.test_check_location_01,
        )

    def test_get_child_locations_with_incorrrect_extra_domain(self):
        """Return no child locations when an incorrect extra domain is given, no error is thrown"""
        aux_domain = [("name", "=", "Not a location")]
        self.assertFalse(self.test_picking_pick._get_child_dest_locations(aux_domain=aux_domain))

    def test_create_picking_no_moves(self):
        """Create a picking from picking type but has no moves created as no products_info given"""
        pick = self.Picking.create_picking(picking_type=self.picking_type_pick)
        # Check pick created with correct picking type
        self.assertEqual(len(pick), 1)
        self.assertEqual(pick.picking_type_id, self.picking_type_pick)
        # Check default pick locations
        self.assertEqual(pick.location_id, self.stock_location)
        self.assertEqual(pick.location_dest_id, self.check_location)
        # Check the number of moves is zero
        self.assertEqual(len(pick.move_lines), 0)

    def test_create_picking_success_simple(self):
        """Create a picking from picking type with two products in state draft"""
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 50)
        products = self.apple | self.banana
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 2},
                {"product": self.banana, "uom_qty": 4},
            ],
        )
        # Check default pick locations
        self.assertEqual(pick.location_id, self.stock_location)
        self.assertEqual(pick.location_dest_id, self.check_location)
        # Check products
        self.assertEqual(pick.move_lines.product_id, products)
        # State is in draft
        self.assertEqual(pick.state, "draft")
        # Check batch not created
        self.assertFalse(pick.batch_id)

    def test_create_picking_success_custom_locations(self):
        """Create a picking with non-default locations and confirm"""
        products = self.apple | self.banana
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 2},
                {"product": self.banana, "uom_qty": 4},
            ],
            location_id=self.test_stock_location_01.id,
            location_dest_id=self.test_goodsout_location_01.id,
            confirm=True,
            assign=False,
            priority="0",
            create_batch=True,
        )
        # Check non-default pick locations
        self.assertEqual(pick.location_id, self.test_stock_location_01)
        self.assertEqual(pick.location_dest_id, self.test_goodsout_location_01)
        # Check products
        self.assertEqual(pick.move_lines.product_id, products)
        # Check state
        self.assertEqual(pick.state, "confirmed")
        # Check priority
        self.assertEqual(pick.priority, "0")
        # Check batch created
        self.assertTrue(pick.batch_id)

    def test_create_multiple_pickings(self):
        """Create multiple pickings with non-default locations and priority"""
        products = self.apple | self.banana
        picks = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                [{"product": self.apple, "uom_qty": 2}, {"product": self.banana, "uom_qty": 4}],
                [{"product": self.apple, "uom_qty": 1}, {"product": self.banana, "uom_qty": 1}],
            ],
            location_id=self.test_stock_location_01.id,
            location_dest_id=self.test_goodsout_location_01.id,
            priority="0",
            create_batch=True,
            confirm=True,
        )
        # Correct number of picks
        self.assertEqual(len(picks), 2)
        # Check default locations for picks
        self.assertEqual(picks.location_id, self.test_stock_location_01)
        self.assertEqual(picks.location_dest_id, self.test_goodsout_location_01)
        # Check products
        self.assertEqual(picks.move_lines.product_id, products)
        # Check state
        self.assertEqual(picks.mapped("state"), ["confirmed"] * len(picks))
        # Check priority
        self.assertEqual(picks.mapped("priority"), ["0"] * len(picks))
        # Check batch created
        self.assertTrue(picks.batch_id)

    def test_prepare_and_create_move(self):
        """Prepare and create a single move"""
        pick = self.create_picking(self.picking_type_goods_in)
        move_values = self.Picking._prepare_move(
            pick, [[{"product": self.elderberry, "uom_qty": 10}]]
        )
        # Check the prepared move_values are correct
        self.assertEqual(len(move_values), 1)
        self.assertEqual(move_values[0], self._get_expected_move_values(pick, self.elderberry, 10))
        # Check create move
        new_move = self.Picking._create_move(move_values)
        self.assertEqual(len(new_move), 1)
        self.assertEqual(new_move.product_qty, 10)

    def test_prepare_and_create_multiple_moves(self):
        """Prepare and create multiple moves"""
        products_info = [
            [{"product": self.apple, "uom_qty": 10}],
            [{"product": self.fig, "uom_qty": 10}],
        ]
        pick1 = self.create_picking(self.picking_type_goods_in)
        pick2 = self.create_picking(self.picking_type_goods_in)
        picks = pick1 | pick2
        move_values = self.Picking._prepare_move(picks, products_info)
        # Check the prepared move_values are correct
        expexted_move_values = [
            self._get_expected_move_values(pick, **prod_info[i])
            for pick, prod_info in zip(picks, products_info)
            for i in range(len(prod_info))
        ]
        self.assertEqual(len(move_values), 2)
        self.assertEqual(move_values, expexted_move_values)
        # Check create moves
        new_move = self.Picking._create_move(move_values)
        self.assertEqual(len(new_move), 2)
        self.assertEqual(new_move.product_id, (self.fig | self.apple))

    def test_get_move_lines(self):
        """Test three cases of get_move_lines: when done=None, True and False"""
        # Get all moves and move lines associated to the picking
        move_lines = self.test_picking_in.get_move_lines()
        self.assertEqual(move_lines, self.test_picking_in.move_line_ids)
        moves = self.test_picking_in.move_lines
        # Check the state of the move lines, qty, qty_done
        self.assertEqual(self.test_picking_in.get_move_lines(done=False), move_lines)
        self.assertFalse(self.test_picking_in.get_move_lines(done=True))
        self.assertEqual(move_lines.qty_done, 0)
        self.assertEqual(move_lines.product_qty, 10)
        # Update the associated move, and complete pick
        self.update_move(moves, 10)
        # Check the get move lines function works for done lines
        self.assertEqual(self.test_picking_in.get_move_lines(done=True), move_lines)
        self.assertFalse(self.test_picking_in.get_move_lines(done=False))
        self.assertEqual(move_lines.qty_done, 10)

    def test_requires_backorder_is_false_when_moves_are_fully_covered_when_no_pending_work(self):
        """
        Test that if no move lines are passed, and the qty_done of the move lines covers the moves
        in self then no backorder is required.
        """
        mls = self.test_picking_in.move_line_ids
        # Update move lines
        for ml in mls:
            ml.qty_done = ml.product_uom_qty

        self.assertFalse(self.test_picking_in._requires_backorder(mls=None))

    def test_requires_backorder_is_false_when_moves_are_fully_covered_by_passed_mls(self):
        """
        Test that if the move lines passed are not all done or do not cover the moves
        in the picking, then a backorder is required.
        """
        mls = self.test_picking_in.move_line_ids

        self.assertFalse(self.test_picking_in._requires_backorder(mls=mls))

    def test_requires_backorder_when_moves_not_fully_covered(self):
        """
        Test that if the move lines passed are not all done or do not cover the moves
        in the picking, then a backorder is required.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[
                {"product": self.fig, "uom_qty": 50},
                {"product": self.banana, "uom_qty": 50},
            ],
            assign=True,
        )
        self.assertEqual(pick.state, "assigned")
        # Update a move line
        all_mls = pick.move_line_ids
        all_mls[0].qty_done = 10

        # Check a backorder is needed
        for mls in (None, all_mls[0]):
            with self.subTest(has_mls=bool(mls)):
                self.assertTrue(pick._requires_backorder(mls=mls))

    def test_requires_backorder_when_moves_not_fully_covered_due_to_partially_available(self):
        """Test that if a picking is partially available a backorder is required"""
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 500}],
            assign=True,
        )
        self.assertEqual(len(pick.move_line_ids), 1)
        self.assertEqual(pick.move_lines.state, "partially_available")
        self.assertEqual(pick.state, "assigned")
        # Update a move line
        fig_ml = pick.move_line_ids
        fig_ml.qty_done = fig_ml.product_uom_qty

        # Check a backorder is needed
        for mls in (None, fig_ml):
            with self.subTest(has_mls=bool(mls)):
                self.assertTrue(pick._requires_backorder(mls=mls))

    def test_requires_backorder_when_moves_cancelled(self):
        """
        Test that if a picking is partially cancelled a backorder is required
        only if the remaining mls are incomplete.
        """
        self.create_quant(self.fig.id, self.test_stock_location_01.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 50)
        self.create_quant(self.apple.id, self.test_stock_location_03.id, 50)
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[
                {"product": self.fig, "uom_qty": 50},
                {"product": self.banana, "uom_qty": 50},
                {"product": self.apple, "uom_qty": 50},
            ],
            assign=True,
        )
        moves = pick.move_lines
        self.assertEqual(len(moves), 3)
        self.assertEqual(len(pick.move_line_ids), 3)
        self.assertEqual(pick.state, "assigned")

        # Update the fig move line
        mls = pick.move_line_ids
        fig_ml = mls.filtered(lambda ml: ml.product_id == self.fig)
        fig_ml.qty_done = fig_ml.product_uom_qty
        self.assertEqual(fig_ml.move_id.state, "assigned")

        # Cancel the banana move
        banana_mv = moves.filtered(lambda ml: ml.product_id == self.banana)
        banana_mv._action_cancel()
        self.assertEqual(banana_mv.state, "cancel")

        # Complete the apple move
        apple_mv = moves.filtered(lambda ml: ml.product_id == self.apple)
        apple_mv.move_line_ids.qty_done = apple_mv.move_line_ids.product_uom_qty
        apple_mv.move_line_ids.location_dest_id = self.test_goodsout_location_01
        apple_mv._action_done()
        self.assertEqual(apple_mv.state, "done")

        # Check when nothing passed, or the fig_ml passed, it skips over the
        # requirement for the cancelled move
        for x_mls in (None, fig_ml):
            with self.subTest(has_mls=bool(x_mls)):
                self.assertFalse(pick._requires_backorder(mls=x_mls))

    def test_assert_related_pickings_computed_correctly(self):
        """
        Assert that first/previous/next picking computed fields return expected records
        with the following setup:

        4 picks (A, B, C and D) with the following moves:

        - Pick A - 1 move
        - Pick B - 2 moves, 1st move set to originate from Pick A's move
        - Pick C - 1 move
        - Pick D - 1 move, set to originate from all moves from Pick B and C
        """
        apple_products_info = [{"product": self.apple, "uom_qty": 10}]

        # Create test picks
        pick_a = self.create_picking(self.picking_type_pick, name="Pick A")
        pick_b = self.create_picking(self.picking_type_pick, name="Pick B")
        pick_c = self.create_picking(self.picking_type_pick, name="Pick C")
        pick_d = self.create_picking(self.picking_type_pick, name="Pick D")

        all_picks = pick_a | pick_b | pick_c | pick_d

        # Create moves for picks
        pick_a_move_1 = self.create_move(pick_a, apple_products_info)

        pick_b_move_1 = self.create_move(pick_b, apple_products_info)
        pick_b_move_2 = self.create_move(pick_b, apple_products_info)

        pick_c_move_1 = self.create_move(pick_c, apple_products_info)

        pick_d_move_1 = self.create_move(pick_d, apple_products_info)

        # Set one of Pick B's moves to have originated from Pick A's move
        pick_b_move_1.move_orig_ids = pick_a_move_1

        # Set Pick D's move to have originated from Pick B/C's moves
        pick_d_move_1.move_orig_ids = pick_b_move_1 | pick_b_move_2 | pick_c_move_1

        # Pick Move Relationship Diagram
        #
        # A1
        # |
        # B1________B2_______C1
        # |         |         |
        # |_________D1________|
        #
        # Expected Results From Computed Fields
        #
        # Pick A:
        #   -- First: Pick A (A1 doesn't originate from any move)
        #   -- Prev:  False (A1 doesn't originate from any move)
        #   -- Next:  Pick B (B1 originates from A1)
        #
        # Pick B:
        #   -- First: Pick A and B (B1 originates from A1, but B2 does not originate from any move)
        #   -- Prev:  Pick A (only pick above Pick B in the chain)
        #   -- Next:  Pick D (D1 originates from B1 and B2, no direct link to Pick C)
        #
        # Pick C:
        #   -- First: Pick C (C1 doesn't originate from any move)
        #   -- Prev:  False (C1 doesn't originate from any move)
        #   -- Next:  Pick D (D1 originates from C1)
        #
        # Pick D:
        #   -- First: Pick A, B and C (D1 originates from B2, C1 and B1, which originates from A1)
        #   -- Prev:  Pick B and C (D1 originates from B1, B2 and C1 but has no direct link to A1)
        #   -- Next:  False (No moves originate from D1)

        expected_pickings_by_field = {
            "u_first_picking_ids": {
                pick_a: pick_a,
                pick_b: (pick_a | pick_b),
                pick_c: pick_c,
                pick_d: (pick_a | pick_b | pick_c),
            },
            "u_prev_picking_ids": {
                pick_a: False,
                pick_b: pick_a,
                pick_c: False,
                pick_d: (pick_b | pick_c),
            },
            "u_next_picking_ids": {pick_a: pick_b, pick_b: pick_d, pick_c: pick_d, pick_d: False},
        }

        # Assert that each computed picking field returns the expected result for all picks
        self._assert_picking_related_pickings_match_expected_values(
            all_picks, expected_pickings_by_field
        )

    def test_assert_created_backorders_computed_correctly(self):
        """Assert that Created Backorders field is computed correctly"""
        apple_qty = 1
        self.create_quant(self.apple.id, self.test_stock_location_01.id, apple_qty)

        # Create picking with demand for more apple's than are in stock
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "uom_qty": apple_qty + 1}],
            location_dest_id=self.test_received_location_01.id,
            location_id=self.test_stock_location_01.id,
            assign=True,
        )

        # Set quantity done which doesn't match the full demand
        pick.move_line_ids[0].qty_done = apple_qty

        # Validate pick which will create backorder for remaining apple quantity
        pick._action_done()

        # Assert that a backorder was generated
        expected_backorder = self.Picking.search([("backorder_id", "=", pick.id)], limit=1)
        self.assertEqual(
            len(expected_backorder),
            1,
            "A backorder should have been generated from pick being validated",
        )

        # Assert that Created Backorders field picks up the previously generated backorder
        self.assertEqual(
            pick.u_created_backorder_ids,
            expected_backorder,
            f"Created Backorders {pick.u_created_backorder_ids} does not match "
            f"expected backorder: {expected_backorder}",
        )

    def test_assert_picking_quantities_computed_correctly(self):
        """Assert that qty todo/done and package discrepancies fields are computed correctly"""
        apple_qty = 10
        apple_qty_per_line = apple_qty / 2

        # Create quants for apples in two separate packages
        pack1 = self.create_package()
        pack2 = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, apple_qty_per_line, package_id=pack1.id
        )
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, apple_qty_per_line, package_id=pack2.id
        )

        # Create picking with demand for all apples in stock, split over 2 lines
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": apple_qty_per_line},
                {"product": self.apple, "uom_qty": apple_qty_per_line},
            ],
            location_dest_id=self.test_received_location_01.id,
            location_id=self.test_stock_location_01.id,
            assign=True,
        )

        self.assertEqual(pick.u_quantity_done, 0)
        self.assertEqual(pick.u_total_quantity, apple_qty)
        self.assertTrue(pick.u_has_discrepancies)

        # Fulfil 1st move line
        pick.move_line_ids[0].qty_done = apple_qty_per_line

        self.assertEqual(
            pick.u_quantity_done,
            apple_qty_per_line,
            "Quantity done should match apple per line quantity",
        )
        self.assertTrue(pick.u_has_discrepancies)

        # Fulfil 2nd move line which should mean pick is no longer flagged as having discrepancies
        pick.move_line_ids[1].qty_done = apple_qty_per_line

        self.assertEqual(pick.u_quantity_done, apple_qty)
        self.assertFalse(pick.u_has_discrepancies)


class TestDifferentUoMinPickings(TestStockPickingCommon):
    @classmethod
    def setUpClass(cls):
        super(TestDifferentUoMinPickings, cls).setUpClass()
        Uom = cls.env["uom.uom"]
        unit = cls.env.ref("uom.product_uom_categ_unit")
        cls.half_dozen = Uom.create(
            {
                "name": "HalfDozen",
                "category_id": unit.id,
                "factor_inv": 6,
                "uom_type": "bigger",
                "rounding": 1.0,
            }
        )

        cls.uom_dozen = cls.env.ref("uom.product_uom_dozen")
        cls.cherry.uom_id = cls.uom_dozen.id

        cls.create_quant(cls.banana.id, cls.test_stock_location_01.id, 120)
        cls.create_quant(cls.cherry.id, cls.test_stock_location_01.id, 120)

        cls.products = cls.cherry | cls.banana

    def _create_product_infos(self, uom_id=None):
        return [
            {"product": self.cherry, "uom_qty": 6, "uom_id": uom_id},
            {"product": self.banana, "uom_qty": 6, "uom_id": uom_id},
        ]

    def test_move_created_with_two_move_lines_and_default_uom(self):
        """
        Prepare and create multiple moves with different UoMs.

        Create a single goods in picking with:
            - 6 Bananas
            - 6 Cherries
        all with unitary UoM.
        """
        pick = self.create_picking(self.picking_type_goods_in)
        move_values = self.Picking._prepare_move(pick, [self._create_product_infos()])
        # Check the prepared move_values are correct
        self.assertEqual(len(move_values), 2)
        for product in self.products:
            with self.subTest(product=product.name):
                self.assertEqual(
                    [mv for mv in move_values if mv.get("product_id") == product.id][0],
                    self._get_expected_move_values(pick, product, 6),
                )

        # Check created move is as expected
        new_moves = self.Picking._create_move(move_values)
        self.assertEqual(len(new_moves), 2)
        banana_mv = new_moves.filtered(lambda mv: mv.product_id == self.banana)
        cherry_mv = new_moves.filtered(lambda mv: mv.product_id == self.cherry)

        # Check the moves have the same UoM as the product
        self.assertEqual(banana_mv.product_uom, self.banana.uom_id)
        self.assertEqual(cherry_mv.product_uom, self.cherry.uom_id)

        # Check the quantities of the moves
        self.assertEqual(banana_mv.product_qty, 6)
        self.assertEqual(banana_mv.product_uom_qty, 6)
        self.assertEqual(cherry_mv.product_qty, 6)
        self.assertEqual(cherry_mv.product_uom_qty, 6)

    def test_prepare_and_create_move_with_move_uom(self):
        """Prepare and create multiple moves with different UoMs, but try to sell everything
        in a single UoM.
        Here we have:
            * banana - units
            * cherry - dozens
        Try to sell things in boxes of 6
        """
        pick = self.create_picking(self.picking_type_goods_in)
        move_values = self.Picking._prepare_move(
            pick, [self._create_product_infos(uom_id=self.half_dozen.id)]
        )
        # Check the prepared move_values are correct
        self.assertEqual(len(move_values), 2)
        for product in self.products:
            with self.subTest(product=product.name):
                self.assertEqual(
                    [mv for mv in move_values if mv.get("product_id") == product.id][0],
                    self._get_expected_move_values(pick, product, 6, uom_id=self.half_dozen.id),
                )

        # Check created move is as expected
        new_moves = self.Picking._create_move(move_values)
        self.assertEqual(len(new_moves), 2)
        banana_mv = new_moves.filtered(lambda mv: mv.product_id == self.banana)
        cherry_mv = new_moves.filtered(lambda mv: mv.product_id == self.cherry)

        # Check the moves have half dozen UoM
        self.assertEqual(new_moves.product_uom, self.half_dozen)
        self.assertNotEqual(self.half_dozen, self.banana.uom_id)
        self.assertNotEqual(self.half_dozen, self.cherry.uom_id)

        # Check the quantities of the moves
        # Requested 36 items of everything, bananas are units so expect 36
        # Cherries come in dozens, so expect 3 packs of 12
        self.assertEqual(banana_mv.product_qty, 36)
        self.assertEqual(banana_mv.product_uom_qty, 6)
        self.assertEqual(cherry_mv.product_qty, 3)
        self.assertEqual(cherry_mv.product_uom_qty, 6)

    def test_complete_picking_with_product_uoms(self):
        """
        Create and complete a picking with multiple products with different UoMs
        """
        self.assertNotEqual(self.uom_dozen, self.banana.uom_id)
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=self._create_product_infos(),
            assign=True,
        )
        # State is assigned
        self.assertEqual(pick.state, "assigned")
        # Check the moves and move lines are in UoM of the product
        for mv in pick.move_lines:
            with self.subTest(product=mv.product_id.name):
                self.assertEqual(mv.product_qty, 6)
                self.assertEqual(mv.product_uom_qty, 6)
        for ml in pick.move_line_ids:
            with self.subTest(product=ml.product_id.name):
                self.assertEqual(ml.product_qty, 6)
                self.assertEqual(ml.product_uom_qty, 6)

        # Complete the picking
        pick.move_line_ids.qty_done = 6
        pick.move_line_ids.location_dest_id = self.test_goodsout_location_01
        pick._action_done()
        self.assertEqual(pick.state, "done")
        # Check the total quantity in the picking, relative to the UoM of the products
        self.assertEqual(pick.u_total_quantity, 12)
        self.assertEqual(pick.u_quantity_done, 12)

    def test_complete_picking_with_specific_uom(self):
        """
        Create and complete a picking with a specific UoM
        Here we have:
            * banana - units
            * cherry - dozens
        Try to sell things in boxes of 6.

        Complete a picking of 6 boxes of 6 - product_uom_qty = 6
        Expect
          * banana: product_qty = 36 (36 / 36)
          * cherry: product_qty = 3 (36 / 12)

        """
        self.assertNotEqual(self.uom_dozen, self.banana.uom_id)
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=self._create_product_infos(uom_id=self.half_dozen.id),
            assign=True,
        )

        # Check the moves and move lines have the UoM of the move not the move line
        moves = pick.move_lines
        banana_move = moves.filtered(lambda m: m.product_id == self.banana)
        cherry_move = moves.filtered(lambda m: m.product_id == self.cherry)
        self.assertEqual(banana_move.product_qty, 36)
        self.assertEqual(banana_move.product_uom_qty, 6)
        self.assertEqual(cherry_move.product_qty, 3)
        self.assertEqual(cherry_move.product_uom_qty, 6)

        mls = pick.move_line_ids
        cherry_ml = mls.filtered(lambda ml: ml.product_id == self.cherry)
        banana_ml = mls.filtered(lambda ml: ml.product_id == self.banana)
        self.assertEqual(banana_ml.product_qty, 36)
        self.assertEqual(banana_ml.product_uom_qty, 6)
        self.assertEqual(cherry_ml.product_qty, 3)
        self.assertEqual(cherry_ml.product_uom_qty, 6)

        # Pick things in terms of the move UoM
        pick.move_line_ids.qty_done = 6
        pick.move_line_ids.location_dest_id = self.test_goodsout_location_01
        pick._action_done()
        self.assertEqual(pick.state, "done")

        # Check the total quantity in the picking, relative to the UoM of the move
        # not the products.
        # So this is the sum of the product_uom_qty of the moves.
        self.assertEqual(pick.u_total_quantity, 12)
        self.assertEqual(pick.u_quantity_done, 12)


class TestStockPickingUnlinkingEmpties(common.BaseUDES):
    """
    Tests for unlinking empty pickings functionality.

    This class tests StockPicking.unlink_empty() directly, and indirectly
    StockPicking.get_empty_pickings().
    """

    def test_unlinks_tagged_empty_pickings_in_recordset(self):
        """Empty pickings with u_is_empty = True in a recordset are unlinked."""
        pick = self.create_picking(self.picking_type_pick)
        pick.u_is_empty = True

        result = pick.unlink_empty()

        self.assertFalse(result)

    def test_does_not_unlink_untagged_empty_picking(self):
        """An empty picking with u_is_empty = False will not be deleted."""
        pick = self.create_picking(self.picking_type_pick)
        pick.u_is_empty = False

        result = pick.unlink_empty()

        self.assertEqual(pick, result)

    def test_raises_exception_on_unlink_non_empty_pickings(self):
        """Non-empty pickings in a recordset are not unlinked."""
        pick = self.create_picking(
            self.picking_type_pick, products_info=[{"product": self.apple, "uom_qty": 1}]
        )
        pick.u_is_empty = True

        with self.assertRaisesRegex(
            ValidationError, r"Trying to unlink non empty pickings: \[\d+\]"
        ):
            pick.unlink_empty()

    def test_unlinks_empty_pickings_if_picking_type_configured(self):
        """Empty pickings for a picking type are unlinked if auto-unlinking is enabled."""
        Picking = self.env["stock.picking"]

        self.picking_type_pick.u_auto_unlink_empty = True
        pick = self.create_picking(self.picking_type_pick)
        pick.u_is_empty = True

        Picking.unlink_empty()

        self.assertFalse(pick.exists())

    def test_does_not_unlink_empty_pickings_if_picking_type_not_configured(self):
        """Empty pickings for a picking type remain if auto-unlinking is disabled."""
        Picking = self.env["stock.picking"]

        self.picking_type_pick.u_auto_unlink_empty = False
        pick = self.create_picking(self.picking_type_pick)
        pick.u_is_empty = True

        Picking.unlink_empty()

        self.assertTrue(pick.exists())


class TestBatchUserName(common.BaseUDES):
    """Test Batch User takes value expected and changes when expected"""

    @classmethod
    def setUpClass(cls):
        super(TestBatchUserName, cls).setUpClass()
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)

        cls.batch = cls.create_batch(user=cls.env.user)

        cls._pick_info = [{"product": cls.apple, "uom_qty": 5}]
        cls.picking = cls.create_picking(
            picking_type=cls.picking_type_pick, products_info=cls._pick_info, confirm=True
        )

        cls.stock_manager = cls.create_user(
            name="Stock Manager",
            login="Stock Manager Dude",
            groups_id=[(6, 0, [cls.env.ref("stock.group_stock_manager").id])],
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


class TestStockPickingValidatePicking(common.BaseUDES):
    """Test validate picking"""

    @classmethod
    def setUpClass(cls):
        super(TestStockPickingValidatePicking, cls).setUpClass()
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)

        cls._pick_info = [{"product": cls.apple, "uom_qty": 5}]
        cls.picking = cls.create_picking(
            picking_type=cls.picking_type_pick,
            products_info=cls._pick_info,
            confirm=True,
            assign=True,
        )

    def move_line_done(self, move_line, quantity, user=False):
        """Update quantity done of a move line, if user is provided update the context"""
        if user:
            # Temporary change the user of the object
            original_user = self.env.user
            move_line = move_line.with_user(user)
        move_line.qty_done = quantity
        new_ml = move_line._split()
        if user:
            # Change user back to the original
            new_ml = new_ml.with_user(original_user)
        return new_ml

    def test_assert_valid_state(self):
        """Validating a picking in state done raises an error."""
        pick = self.picking
        pick.state = "done"
        with self.assertRaises(ValidationError) as e:
            backorder = pick.validate_picking()
        msg = f"Wrong state done for {pick.log_name()}"
        self.assertEqual(e.exception.args[0], msg)

    def test_force_validate(self):
        """Force validating a picking will mark as done all its move lines and then
        validate the picking.
        """
        pick = self.picking
        mls = pick.move_line_ids
        self.assertEqual(mls.qty_done, 0)
        pick.move_line_ids.location_dest_id = self.test_goodsout_location_01
        backorder = pick.validate_picking(force_validate=True)
        # No backorder
        self.assertFalse(backorder)
        # Original picking in state done
        self.assertEqual(pick.state, "done")

    def test_create_backorder(self):
        """Validating a picking with a move partially done raise validation error unless
        create_backorer=True is provided.
        """
        pick = self.picking
        mls = pick.move_line_ids
        # Create uncompleted move line done by admin
        new_mls = self.move_line_done(mls, 2)
        # Validate without parameter raises error
        with self.assertRaises(ValidationError) as e:
            backorder = pick.validate_picking()
        msg = (
            f"Cannot validate {pick.log_name()} because there are move lines todo and "
            f"backorder not allowed"
        )
        self.assertEqual(e.exception.args[0], msg)
        # Validate with parameter works fine
        pick.move_line_ids.location_dest_id = self.test_goodsout_location_01
        backorder = pick.validate_picking(create_backorder=True)
        # Backorder created with the uncompleted move line
        self.assertNotEqual(backorder, pick)
        self.assertEqual(backorder.state, "assigned")
        self.assertEqual(backorder.move_line_ids, new_mls)
        # Original picking in state done
        self.assertEqual(pick.state, "done")

    def test_multi_users_enabled(self):
        """Validating a picking with multi users enabled will create a backorder for all the lines
        not done or done by other users
        """
        other_user = self.create_user(name="Other user", login="Other Dude")

        pick = self.picking
        mls = pick.move_line_ids
        # Create uncompleted move line done by admin
        new_mls = self.move_line_done(mls, 2)
        # Create uncompleted move line done by admin
        new_mls_2 = self.move_line_done(new_mls, 2, other_user)
        expected_backorder_mls = new_mls | new_mls_2
        # Enable multiple users
        pick.picking_type_id.u_multi_users_enabled = True
        # Validate picking
        pick.move_line_ids.location_dest_id = self.test_goodsout_location_01
        res_pick = self.picking.validate_picking()
        # Backorder created with the uncompleted move line and move line done by other_user
        self.assertNotEqual(res_pick, pick)
        self.assertEqual(res_pick.state, "assigned")
        self.assertEqual(res_pick.move_line_ids, expected_backorder_mls)
        # Original picking in state done
        self.assertEqual(pick.state, "done")


class TestStockPickingPriorities(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPickingPriorities, cls).setUpClass()
        cls.create_quant(cls.fig.id, cls.test_stock_location_02.id, 100)

        # first pick
        cls.pick = cls.create_picking(
            picking_type=cls.picking_type_pick,
            products_info=[{"product": cls.fig, "uom_qty": 10}],
            location_id=cls.test_stock_location_02.id,
            confirm=True,
            assign=True,
            priority="0",
        )

        # second pick
        cls.pick2 = cls.create_picking(
            picking_type=cls.picking_type_pick,
            products_info=[{"product": cls.fig, "uom_qty": 10}],
            location_id=cls.test_stock_location_02.id,
            confirm=True,
            assign=True,
            priority="1",
        )

    def test_priority_zero_remains_on_done_picking(self):
        """
        Test that priority 0 is not overwritten on done pickings.
        """
        self.complete_picking(self.pick)
        self.assertEqual(self.pick.priority, "0")

    def test_priority_zero_remains_on_cancelled_picking(self):
        """
        Test that priority 0 is not overwritten on cancelled pickings.
        """
        self.pick.action_cancel()
        self.assertEqual(self.pick.priority, "0")

    @unittest.skip("Needs odoo-tester:14.0 image rebuilding")
    def test_priority_one_remains_on_done_picking(self):
        """
        Test that priority 1 is not overwritten on done pickings.
        """
        self.complete_picking(self.pick2)
        self.assertEqual(self.pick2.priority, "1")

    def test_priority_one_remains_on_cancelled_picking(self):
        """
        Test that priority 1 is not overwritten on cancelled pickings.
        """
        self.pick2.action_cancel()
        self.assertEqual(self.pick2.priority, "1")

    def test_picking_can_be_deleted_in_draft(self):
        """
        Test that a picking can be deleted in draft state
        """
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 10}],
            location_id=self.test_stock_location_02.id,
            confirm=False,
            assign=False,
            priority="0",
        )
        self.assertEqual(pick.state, "draft")
        pick.unlink()
        self.assertFalse(pick.exists())

    def test_picking_cannot_be_deleted_outside_draft(self):
        """
        Test that a picking cannot be deleted in states: confirmed, waiting, assigned, done, cancel
        """
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 10}],
            location_id=self.test_stock_location_02.id,
            confirm=True,
            assign=False,
            priority="0",
        )
        self.assertEqual(pick.state, "confirmed")
        with self.assertRaises(UserError):
            pick.unlink()

        next_picking_waiting = pick.u_next_picking_ids
        self.assertEqual(next_picking_waiting.state, "waiting")
        with self.assertRaises(UserError):
            pick.unlink()

        pick.action_assign()
        self.assertEqual(pick.state, "assigned")
        with self.assertRaises(UserError):
            pick.unlink()
        self.complete_picking(pick)
        self.assertEqual(pick.state, "done")
        with self.assertRaises(UserError):
            pick.unlink()

        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 10}],
            location_id=self.test_stock_location_02.id,
            confirm=False,
            assign=False,
            priority="0",
        )
        pick.action_cancel()
        self.assertEqual(pick.state, "cancel")
        with self.assertRaises(UserError):
            pick.unlink()

    def test_picking_can_be_deleted_with_bypass_state_check(self):
        """
        Test that a picking can be deleted with context variable
        """
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 10}],
            location_id=self.test_stock_location_02.id,
            confirm=False,
            assign=False,
            priority="0",
        )
        pick.action_cancel()
        self.assertEqual(pick.state, "cancel")
        pick.with_context(bypass_state_check=True).unlink()
        self.assertFalse(pick.exists())


class TestStockPickingProcurementGroup(TestStockPickingCommon):
    def test_procurement_group_created(self):
        """Procurement group created when u_create_procurement_group is enabled"""
        # Goods-in and Pick pickings created at setup do not have a group
        self.assertFalse(self.test_picking_in.group_id)
        self.assertFalse(self.test_picking_pick.group_id)
        # Change flag to True for newly created Goods-in and Pick pickings
        self.picking_type_goods_in.u_create_procurement_group = True
        self.picking_type_pick.u_create_procurement_group = True
        products_info = [{"product": self.apple, "uom_qty": 10}]
        new_test_picking_in = self.create_picking(
            self.picking_type_goods_in,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,
        )
        new_test_picking_pick = self.create_picking(
            self.picking_type_pick, products_info=products_info, confirm=True
        )
        # Newly created Goods-in and Pick pickings do have a group
        self.assertEqual(new_test_picking_in.group_id.name, new_test_picking_in.name)
        self.assertEqual(new_test_picking_pick.group_id.name, new_test_picking_pick.name)
