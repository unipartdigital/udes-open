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
        pick._action_done()
        bk_picking_1 = pick.u_created_backorder_ids
        bk_picking_1.move_lines[0].quantity_done = 10
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
        pick._action_done()
        moves = pick.move_lines

        # Assert the move lines are different
        self.assertNotEqual(pick.move_line_ids, banana_ml | fig_ml)
        old_mls = MoveLine.search([("id", "in", (banana_ml | fig_ml).ids)])
        self.assertFalse(old_mls)

        # Check the moves still exist for completeness
        old_moves = Move.search([("id", "in", moves.ids)])
        self.assertEqual(old_moves, moves)

    def test_backorder_move_lines_raises_exception_when_qty_done_in_ml_less_than_product_uom_qty(
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
        pick.move_line_ids.qty_done = 10
        with self.assertRaises(ValidationError) as e, mute_logger("odoo.sql_db"):
            pick._backorder_move_lines()

        # Check the error is as expected
        self.assertEqual(
            e.exception.args[0],
            "You cannot create a backorder for %s with a move line qty less than expected!"
            % pick.name,
        )

    def test_backorder_move_lines_returns_self_when_nothing_done(self):
        """
        When trying to create a backorder with no lines yet complete check it returns
        an empty record set.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 50}],
            assign=True,
        )
        bk_picking = pick._backorder_move_lines()
        self.assertFalse(bk_picking)

    def test_backorder_move_lines_raises_exception_when_nothing_to_backorder(self):
        """
        When trying to create a backorder with no lines left to do ensure
        the ValidationError is correctly raised. Everything has been fulfilled,
        should just validate the picking.
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 50}],
            assign=True,
        )
        pick.move_line_ids.qty_done = 50
        with self.assertRaises(ValidationError) as e, mute_logger("odoo.sql_db"):
            pick._backorder_move_lines()

        # Check the error is as expected
        self.assertEqual(
            e.exception.args[0],
            "There are no move lines within picking %s to backorder" % pick.name,
        )

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

        # Check the original picking and that the orignal move lines exist
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

    def test_backorder_move_lines_propogates_partially_avilable_moves(self):
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

        # Check original pick after backordering, the incoplete moves have been moved out
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
        self.assertFalse(bk_picking.move_line_ids)  # No Move lines as nothing available yet
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
                * fig: 20, 5 reserved, 3 done
                * banana: 10, 5 reserved, 0 done

        Expect:
        Original Pick:
            * fig: 3, 3 reserved, 3 done
        Backorder Pick:
            * fig: 17, 2 reserved, 0 done
            * banana: 10, 5 reserved, 0 done
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

        # Check original pick after backordering, the incoplete moves have been moved out
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
        zone_z = self.Location.create({"name": "Zone Z", "location_id": self.received_location.id})
        loc_a = self.Location.create({"name": "A", "barcode": "LRTESTA", "location_id": zone_z.id})

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
        locations = self.test_goodsout_locations | self.out_location
        self.assertEqual(self.test_picking_pick._get_child_dest_locations(), locations)

    def test_get_child_locations_simple_success_with_extra_domain(self):
        """Get child locations - with extra domain"""
        aux_domain = [("name", "=", self.test_goodsout_location_01.name)]
        self.assertEqual(
            self.test_picking_pick._get_child_dest_locations(aux_domain=aux_domain),
            self.test_goodsout_location_01,
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
        self.assertEqual(pick.location_dest_id, self.out_location)
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
        self.assertEqual(pick.location_dest_id, self.out_location)
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
        # Check default locations for pick
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

    def test_pepare_and_create_move(self):
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

    def test_requires_backorder_simple(self):
        """Simple requires backorder check"""
        # Update moves
        self.test_picking_in.move_lines.quantity_done = 10
        # Check a backorder is not needed when picking move lines are passed to requires_backorder
        mls = self.test_picking_in.move_line_ids
        self.assertFalse(self.test_picking_in._requires_backorder(mls))

    def test_requires_backorder_multi_lines(self):
        """Create picking with multiple lines backorder check"""
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


#     def test_assert_picking_quantities_computed_correctly(self):
#         """Assert that qty todo/done and package discrepancies fields are computed correctly"""
#         apple_qty = 10
#         apple_qty_per_line = apple_qty / 2

#         # Create quants for apples in two separate packages
#         pack1 = self.create_package()
#         pack2 = self.create_package()
#         self.create_quant(
#             self.apple.id, self.test_stock_location_01.id, apple_qty_per_line, package_id=pack1.id
#         )
#         self.create_quant(
#             self.apple.id, self.test_stock_location_01.id, apple_qty_per_line, package_id=pack2.id
#         )

#         # Create picking with demand for all apples in stock, split over 2 lines
#         pick = self.create_picking(
#             self.picking_type_pick,
#             products_info=[
#                 {"product": self.apple, "uom_qty": apple_qty_per_line},
#                 {"product": self.apple, "uom_qty": apple_qty_per_line},
#             ],
#             location_dest_id=self.test_received_location_01.id,
#             location_id=self.test_stock_location_01.id,
#             assign=True,
#         )

#         self.assertEqual(pick.u_quantity_done, 0, "Quantity done should be zero")
#         self.assertEqual(
#             pick.u_total_quantity, apple_qty, "Total quantity should match apple quantity"
#         )
#         self.assertTrue(pick.u_has_discrepancies, "Pick should have discrepancies")

#         # Fulfil 1st move line
#         pick.move_line_ids[0].qty_done = apple_qty_per_line

#         self.assertEqual(
#             pick.u_quantity_done,
#             apple_qty_per_line,
#             "Quantity done should match apple per line quantity",
#         )
#         self.assertTrue(pick.u_has_discrepancies, "Pick should have discrepancies")

#         # Fulfil 2nd move line which should mean pick is no longer flagged as having discrepancies
#         pick.move_line_ids[1].qty_done = apple_qty_per_line

#         self.assertEqual(
#             pick.u_quantity_done, apple_qty, "Quantity done should match apple quantity"
#         )
#         self.assertFalse(pick.u_has_discrepancies, "Pick should not have discrepancies")


# class TestStockPickingUoM(TestStockPickingCommon):
#     @classmethod
#     def setUpClass(cls):
#         super(TestStockPickingUoM, cls).setUpClass()
#         Uom = cls.env["uom.uom"]
#         unit = cls.env.ref("uom.product_uom_categ_unit")
#         cls.half_dozen = Uom.create(
#             {
#                 "name": "HalfDozen",
#                 "category_id": unit.id,
#                 "factor_inv": 6,
#                 "uom_type": "bigger",
#                 "rounding": 1.0,
#             }
#         )

#         cls.uom_dozen = cls.env.ref("uom.product_uom_dozen")
#         cls.cherry.uom_id = cls.uom_dozen.id

#         cls.create_quant(cls.banana.id, cls.test_stock_location_01.id, 120)
#         cls.create_quant(cls.cherry.id, cls.test_stock_location_01.id, 120)

#         cls.products = cls.cherry | cls.banana

#     def _create_product_infos(self, uom_id=None):
#         return [
#             {"product": self.cherry, "uom_qty": 6, "uom_id": uom_id},
#             {"product": self.banana, "uom_qty": 6, "uom_id": uom_id},
#         ]

#     def test_pepare_and_create_move(self):
#         """Prepare and create multiple moves with different UoMs"""
#         pick = self.create_picking(self.picking_type_goods_in)
#         move_values = self.Picking._prepare_move(pick, [self._create_product_infos()])
#         # Check the prepared move_values are correct
#         self.assertEqual(len(move_values), 2)
#         for product in self.products:
#             with self.subTest(product=product.name):
#                 self.assertEqual(
#                     [mv for mv in move_values if mv.get("product_id") == product.id][0],
#                     self._get_expected_move_values(pick, product, 6),
#                 )

#         # Check created move is as expected
#         new_moves = self.Picking._create_move(move_values)
#         self.assertEqual(len(new_moves), 2)
#         banana_mv = new_moves.filtered(lambda mv: mv.product_id == self.banana)
#         cherry_mv = new_moves.filtered(lambda mv: mv.product_id == self.cherry)

#         # Check the moves have the same UoM as the product
#         self.assertEqual(banana_mv.product_uom, self.banana.uom_id)
#         self.assertEqual(cherry_mv.product_uom, self.cherry.uom_id)

#         # Check the quantities of the moves
#         self.assertEqual(banana_mv.product_qty, 6)
#         self.assertEqual(banana_mv.product_uom_qty, 6)
#         self.assertEqual(cherry_mv.product_qty, 6)
#         self.assertEqual(cherry_mv.product_uom_qty, 6)

#     def test_pepare_and_create_move_with_move_uom(self):
#         """Prepare and create multiple moves with different UoMs, but try to sell everything
#         in a single UoM.
#         Here we have:
#             * banana - units
#             * cherry - dozens
#         Try to sell things in boxes of 6
#         """
#         pick = self.create_picking(self.picking_type_goods_in)
#         move_values = self.Picking._prepare_move(
#             pick, [self._create_product_infos(uom_id=self.half_dozen.id)]
#         )
#         # Check the prepared move_values are correct
#         self.assertEqual(len(move_values), 2)
#         for product in self.products:
#             with self.subTest(product=product.name):
#                 self.assertEqual(
#                     [mv for mv in move_values if mv.get("product_id") == product.id][0],
#                     self._get_expected_move_values(pick, product, 6, uom_id=self.half_dozen.id),
#                 )

#         # Check created move is as expected
#         new_moves = self.Picking._create_move(move_values)
#         self.assertEqual(len(new_moves), 2)
#         banana_mv = new_moves.filtered(lambda mv: mv.product_id == self.banana)
#         cherry_mv = new_moves.filtered(lambda mv: mv.product_id == self.cherry)

#         # Check the moves have half dozen UoM
#         self.assertEqual(new_moves.product_uom, self.half_dozen)
#         self.assertNotEqual(self.half_dozen, self.banana.uom_id)
#         self.assertNotEqual(self.half_dozen, self.cherry.uom_id)

#         # Check the quantities of the moves
#         # Requested 36 items of everything, bananas are units so expect 36
#         # Cherries come in dozens, so expect 3 packs of 12
#         self.assertEqual(banana_mv.product_qty, 36)
#         self.assertEqual(banana_mv.product_uom_qty, 6)
#         self.assertEqual(cherry_mv.product_qty, 3)
#         self.assertEqual(cherry_mv.product_uom_qty, 6)

#     def test_complete_picking_with_product_uoms(self):
#         """
#         Create and complete a picking with multiple products with different UoMs
#         """
#         self.assertNotEqual(self.uom_dozen, self.banana.uom_id)
#         pick = self.Picking.create_picking(
#             picking_type=self.picking_type_pick,
#             products_info=self._create_product_infos(),
#             assign=True,
#         )
#         # State is assigned
#         self.assertEqual(pick.state, "assigned")
#         # Check the moves and move lines are in UoM of the product
#         for mv in pick.move_lines:
#             with self.subTest(product=mv.product_id.name):
#                 self.assertEqual(mv.product_qty, 6)
#                 self.assertEqual(mv.product_uom_qty, 6)
#         for ml in pick.move_line_ids:
#             with self.subTest(product=ml.product_id.name):
#                 self.assertEqual(ml.product_qty, 6)
#                 self.assertEqual(ml.product_uom_qty, 6)

#         # Complete the picking
#         pick.move_line_ids.qty_done = 6
#         pick._action_done()
#         self.assertEqual(pick.state, "done")
#         # Check the total quantity in the picking, relative to the UoM of the products
#         self.assertEqual(pick.u_total_quantity, 12)
#         self.assertEqual(pick.u_quantity_done, 12)

#     def test_complete_picking_with_specific_uom(self):
#         """
#         Create and complete a picking with a specific UoM
#         Here we have:
#             * banana - units
#             * cherry - dozens
#         Try to sell things in boxes of 6.

#         Complete a picking of 6 boxes of 6 - product_uom_qty = 6
#         Expect
#           * banana: product_qty = 36 (36 / 36)
#           * cherry: product_qty = 3 (36 / 12)

#         """
#         self.assertNotEqual(self.uom_dozen, self.banana.uom_id)
#         pick = self.Picking.create_picking(
#             picking_type=self.picking_type_pick,
#             products_info=self._create_product_infos(uom_id=self.half_dozen.id),
#             assign=True,
#         )

#         # Check the moves and move lines have the UoM of the move not the move line
#         moves = pick.move_lines
#         banana_move = moves.filtered(lambda m: m.product_id == self.banana)
#         cherry_move = moves.filtered(lambda m: m.product_id == self.cherry)
#         self.assertEqual(banana_move.product_qty, 36)
#         self.assertEqual(banana_move.product_uom_qty, 6)
#         self.assertEqual(cherry_move.product_qty, 3)
#         self.assertEqual(cherry_move.product_uom_qty, 6)

#         mls = pick.move_line_ids
#         cherry_ml = mls.filtered(lambda ml: ml.product_id == self.cherry)
#         banana_ml = mls.filtered(lambda ml: ml.product_id == self.banana)
#         self.assertEqual(banana_ml.product_qty, 36)
#         self.assertEqual(banana_ml.product_uom_qty, 6)
#         self.assertEqual(cherry_ml.product_qty, 3)
#         self.assertEqual(cherry_ml.product_uom_qty, 6)

#         # Pick things in terms of the move UoM
#         pick.move_line_ids.qty_done = 6
#         pick._action_done()
#         self.assertEqual(pick.state, "done")

#         # Check the total quantity in the picking, relative to the UoM of the move
#         # not the products.
#         # So this is the sum of the product_uom_qty of the moves.
#         self.assertEqual(pick.u_total_quantity, 12)
#         self.assertEqual(pick.u_quantity_done, 12)


# class TestStockPickingUnlinkingEmpties(common.BaseUDES):
#     """
#     Tests for unlinking empty pickings functionality.

#     This class tests StockPicking.unlink_empty() directly, and indirectly
#     StockPicking.get_empty_pickings().
#     """

#     def test_unlinks_tagged_empty_pickings_in_recordset(self):
#         """Empty pickings with u_is_empty = True in a recordset are unlinked."""
#         pick = self.create_picking(self.picking_type_pick)
#         pick.u_is_empty = True

#         result = pick.unlink_empty()

#         self.assertFalse(result)

#     def test_does_not_unlink_untagged_empty_picking(self):
#         """An empty picking with u_is_empty = False will not be deleted."""
#         pick = self.create_picking(self.picking_type_pick)
#         pick.u_is_empty = False

#         result = pick.unlink_empty()

#         self.assertEqual(pick, result)

#     def test_raises_exception_on_unlink_non_empty_pickings(self):
#         """Non-empty pickings in a recordset are not unlinked."""
#         pick = self.create_picking(
#             self.picking_type_pick, products_info=[{"product": self.apple, "uom_qty": 1}]
#         )
#         pick.u_is_empty = True

#         with self.assertRaisesRegex(
#             ValidationError, r"Trying to unlink non empty pickings: \[\d+\]"
#         ):
#             pick.unlink_empty()

#     def test_unlinks_empty_pickings_if_picking_type_configured(self):
#         """Empty pickings for a picking type are unlinked if auto-unlinking is enabled."""
#         Picking = self.env["stock.picking"]

#         self.picking_type_pick.u_auto_unlink_empty = True
#         pick = self.create_picking(self.picking_type_pick)
#         pick.u_is_empty = True

#         Picking.unlink_empty()

#         self.assertFalse(pick.exists())

#     def test_does_not_unlink_empty_pickings_if_picking_type_not_configured(self):
#         """Empty pickings for a picking type remain if auto-unlinking is disabled."""
#         Picking = self.env["stock.picking"]

#         self.picking_type_pick.u_auto_unlink_empty = False
#         pick = self.create_picking(self.picking_type_pick)
#         pick.u_is_empty = True

#         Picking.unlink_empty()

#         self.assertTrue(pick.exists())


# class TestBatchUserName(common.BaseUDES):
#     """Test Batch User takes value expected and changes when expected"""

#     @classmethod
#     def setUpClass(cls):
#         super(TestBatchUserName, cls).setUpClass()
#         cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)

#         cls.batch = cls.create_batch(user=cls.env.user)

#         cls._pick_info = [{"product": cls.apple, "uom_qty": 5}]
#         cls.picking = cls.create_picking(
#             picking_type=cls.picking_type_pick, products_info=cls._pick_info, confirm=True
#         )

#         cls.stock_manager = cls.create_user(name="Stock Manager", login="Stock Manager Dude")

#     def test_correct_batch_user_on_picking_tree_view(self):
#         self.picking.write({"batch_id": self.batch.id})

#         self.assertEqual(self.picking.u_batch_user_id, self.env.user)

#     def test_no_batch_user_on_picking_when_no_batch(self):
#         self.assertEqual(len(self.picking.u_batch_user_id), 0)

#     def test_batch_user_on_picking_changes_when_user_is_changed_on_batch(self):
#         self.picking.write({"batch_id": self.batch.id})

#         self.batch.write({"user_id": self.stock_manager.id})

#         self.assertEqual(self.picking.u_batch_user_id, self.stock_manager)

#     def test_same_batch_user_on_multiple_pickings(self):
#         picking_2 = self.create_picking(
#             picking_type=self.picking_type_pick, products_info=self._pick_info, confirm=True
#         )

#         self.picking.write({"batch_id": self.batch.id})
#         picking_2.write({"batch_id": self.batch.id})

#         self.assertEqual(self.picking.u_batch_user_id, self.env.user)
#         self.assertEqual(picking_2.u_batch_user_id, self.env.user)
