from . import common
from odoo.exceptions import ValidationError


class TestStockPicking(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPicking, cls).setUpClass()
        cls.Picking = cls.env["stock.picking"]
        products_info = [{"product": cls.apple, "qty": 10}]
        cls.test_picking_in = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=products_info,
            confirm=True,
            location_dest_id=cls.test_received_location_01.id,
        )
        cls.test_picking_pick = cls.create_picking(
            cls.picking_type_pick, products_info=products_info, confirm=True
        )

    def _get_expected_move_values(self, pick, product, qty, **kwargs):
        """Helper to get expected move values"""
        expected_move_values = {
            "product_id": product.id,
            "name": product.name,
            "product_uom": product.uom_id.id,
            "product_uom_qty": qty,
            "location_id": pick.location_id.id,
            "location_dest_id": pick.location_dest_id.id,
            "picking_id": pick.id,
            "priority": pick.priority,
            "picking_type_id": pick.picking_type_id.id,
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

    def test01_get_empty_locations(self):
        """Get empty locations - for goods in"""
        self.assertEqual(
            self.test_picking_in.get_empty_locations(),
            self.test_received_location_01,
        )
        # Add stock to a location - to check empty locations obtained
        self.create_quant(
            self.apple.id,
            self.test_received_location_01.id,
            5,
        )
        self.assertFalse(self.test_picking_in.get_empty_locations())

    def test02_get_child_locations_simple_success(self):
        """Get child locations"""
        locations = self.test_goodsout_locations | self.out_location
        self.assertEqual(self.test_picking_pick._get_child_dest_locations(), locations)

    def test03_get_child_locations_simple_success_with_extra_domain(self):
        """Get child locations - with extra domain"""
        aux_domain = [("name", "=", self.test_goodsout_location_01.name)]
        self.assertEqual(
            self.test_picking_pick._get_child_dest_locations(aux_domain=aux_domain),
            self.test_goodsout_location_01,
        )

    def test04_get_child_locations_with_incorrrect_extra_domain(self):
        """Return no child locations when an incorrect extra domain is given, no error is thrown"""
        aux_domain = [("name", "=", "Not a location")]
        self.assertFalse(self.test_picking_pick._get_child_dest_locations(aux_domain=aux_domain))

    def test05_create_picking_no_moves(self):
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

    def test06_create_picking_success_simple(self):
        """Create a picking from picking type with two products in state draft"""
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 50)
        products = self.apple | self.banana
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.apple, "qty": 2},
                {"product": self.banana, "qty": 4},
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

    def test07_create_picking_success_custom_locations(self):
        """Create a picking with non-default locations and confirm"""
        products = self.apple | self.banana
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.apple, "qty": 2},
                {"product": self.banana, "qty": 4},
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

    def test08_create_multiple_pickings(self):
        """Create multiple pickings with non-default locations and priority"""
        products = self.apple | self.banana
        picks = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                [
                    {"product": self.apple, "qty": 2},
                    {"product": self.banana, "qty": 4},
                ],
                [
                    {"product": self.apple, "qty": 1},
                    {"product": self.banana, "qty": 1},
                ],
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

    def test09_pepare_and_create_move(self):
        """Prepare and create a single move"""
        pick = self.create_picking(self.picking_type_goods_in)
        move_values = self.Picking._prepare_move(
            pick,
            [
                [{"product": self.elderberry, "qty": 10}],
            ],
        )
        # Check the prepared move_values are correct
        self.assertEqual(len(move_values), 1)
        self.assertEqual(move_values[0], self._get_expected_move_values(pick, self.elderberry, 10))
        # Check create move
        new_move = self.Picking._create_move(move_values)
        self.assertEqual(len(new_move), 1)
        self.assertEqual(new_move.product_qty, 10)

    def test10_prepare_and_create_multiple_moves(self):
        """Prepare and create multiple moves"""
        products_info = [[{"product": self.apple, "qty": 10}], [{"product": self.fig, "qty": 10}]]
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

    def test11_get_move_lines(self):
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

    def test12_requires_backorder_simple(self):
        """Simple requires backorder check"""
        # Update moves
        self.test_picking_in.move_lines.quantity_done = 10
        # Check a backorder is not needed when picking move lines are passed to requires_backorder
        mls = self.test_picking_in.move_line_ids
        self.assertFalse(self.test_picking_in._requires_backorder(mls))

    def test13_requires_backorder_multi_lines(self):
        """Create picking with multiple lines backorder check"""
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 50)
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "qty": 50}, {"product": self.banana, "qty": 50}],
            location_id=self.test_stock_location_02.id,
        )
        # Update a moves and complete action
        pick.move_lines[0].quantity_done = 10
        # Check a backorder is needed
        mls = pick.move_line_ids
        self.assertTrue(pick._requires_backorder(mls))

    def test14_backorder_move_lines_default_mls(self):
        """Backorder move lines for incomplete pick"""
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 50)
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "qty": 50}, {"product": self.banana, "qty": 50}],
            location_id=self.test_stock_location_02.id,
        )
        pick.move_lines.quantity_done = 10
        product_ids = pick.move_line_ids.mapped("product_id")
        bk_picking = pick._backorder_move_lines()
        # Check backorder pick
        self.assertEqual(bk_picking.backorder_id, pick)
        self.assertEqual(product_ids, bk_picking.move_line_ids.product_id)
        self.assertEqual(bk_picking.move_lines.mapped("product_qty"), [50.0, 50.0])
        self.assertEqual(bk_picking.move_line_ids.mapped("qty_done"), [10.0, 10.0])

    def test15_backorder_move_lines_fig_mls(self):
        """Backorder move lines for incomplete pick, but only for a subset of mls"""
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 50)
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "qty": 50}, {"product": self.banana, "qty": 50}],
            location_id=self.test_stock_location_02.id,
        )
        pick.move_lines[0].quantity_done = 10
        pick.move_lines[1].quantity_done = 5
        bk_picking = pick._backorder_move_lines(
            mls=pick.move_line_ids.filtered(lambda p: p.product_id == self.fig)
        )
        # Check backorder pick
        self.assertEqual(bk_picking.backorder_id, pick)
        self.assertEqual(bk_picking.move_line_ids.product_id, self.fig)
        self.assertEqual(bk_picking.move_lines.product_qty, 50)
        self.assertEqual(bk_picking.move_line_ids.qty_done, 10)
        # Check original pick has those move lines not inserted
        self.assertEqual(pick.move_line_ids.product_id, self.banana)
        self.assertEqual(pick.move_lines.product_qty, 50)
        self.assertEqual(pick.move_line_ids.qty_done, 5)

    def test16_backorder_move_lines_error(self):
        """Backorder move lines raises error when nothing is done"""
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 50)
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[[{"product": self.fig, "qty": 50}, {"product": self.banana, "qty": 50}]],
            location_id=self.test_stock_location_02.id,
        )
        with self.assertRaises(ValidationError) as e:
            pick._backorder_move_lines()
        msg = "There are no move lines within picking %s to backorder" % pick.name
        self.assertEqual(e.exception.args[0], msg)

    def test17_backorder_move_lines_all_qts_done(self):
        """Create a backorder for a picking when all quantities are done
        Old pick is empty, everything moved to backorder pick
        """
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 50)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 50)
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "qty": 50}, {"product": self.banana, "qty": 50}],
            location_id=self.test_stock_location_02.id,
            assign=True,
        )
        pick.move_lines.quantity_done = 50
        product_ids = pick.move_line_ids.mapped("product_id")
        bk_picking = pick._backorder_move_lines()
        # Check backorder pick
        self.assertEqual(bk_picking.backorder_id, pick)
        self.assertEqual(bk_picking.move_line_ids.product_id, product_ids)
        self.assertEqual(bk_picking.move_lines.mapped("product_qty"), [50.0, 50.0])
        self.assertEqual(bk_picking.move_line_ids.mapped("qty_done"), [50.0, 50.0])
        # Check old pick
        self.assertEqual(len(pick.move_line_ids), 0)
        self.assertEqual(len(pick.move_lines), 0)

    def test18_backorder_move_lines_fulfilled_move_not(self):
        """Check when move lines are fulfilled, but the move is partially fulfilled"""
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 8)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 10)
        pick = self.Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[{"product": self.fig, "qty": 20}, {"product": self.banana, "qty": 10}],
            location_id=self.test_stock_location_02.id,
            assign=True,
        )
        pick.move_lines.quantity_done = 10
        # Check pick
        self.assertEqual(pick.move_lines.mapped("state"), ["partially_available", "assigned"])
        self.assertEqual(pick.move_lines.mapped("quantity_done"), [10, 10])
        self.assertEqual(len(pick.move_line_ids), 2)
        bk_picking = pick._backorder_move_lines()
        # Check backorder pick
        self.assertEqual(pick, bk_picking.backorder_id)
        self.assertEqual(bk_picking.move_lines.mapped("state"), ["assigned", "assigned"])
        self.assertEqual(len(bk_picking.move_line_ids), 2)
        self.assertEqual(bk_picking.move_lines.mapped("quantity_done"), [10, 10])
        # Check original pick
        self.assertEqual(pick.move_lines.state, "confirmed")
        self.assertEqual(len(pick.move_line_ids), 0)
        self.assertEqual(pick.move_lines.quantity_done, 0)

    def test19_assert_related_pickings_computed_correctly(self):
        """
        Assert that first/previous/next picking computed fields return expected records
        with the following setup:

        4 picks (A, B, C and D) with the following moves:

        - Pick A - 1 move
        - Pick B - 2 moves, 1st move set to originate from Pick A's move
        - Pick C - 1 move
        - Pick D - 1 move, set to originate from all moves from Pick B and C
        """
        apple_products_info = [{"product": self.apple, "qty": 10}]

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
            "u_next_picking_ids": {
                pick_a: pick_b,
                pick_b: pick_d,
                pick_c: pick_d,
                pick_d: False,
            },
        }

        # Assert that each computed picking field returns the expected result for all picks
        self._assert_picking_related_pickings_match_expected_values(
            all_picks, expected_pickings_by_field
        )

    def test20_assert_created_backorders_computed_correctly(self):
        """Assert that Created Backorders field is computed correctly"""
        apple_qty = 1
        self.create_quant(self.apple.id, self.test_stock_location_01.id, apple_qty)

        # Create picking with demand for more apple's than are in stock
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "qty": apple_qty + 1}],
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

    def test21_assert_picking_quantities_computed_correctly(self):
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
                {"product": self.apple, "qty": apple_qty_per_line},
                {"product": self.apple, "qty": apple_qty_per_line},
            ],
            location_dest_id=self.test_received_location_01.id,
            location_id=self.test_stock_location_01.id,
            assign=True,
        )

        self.assertEqual(pick.u_quantity_done, 0, "Quantity done should be zero")
        self.assertEqual(
            pick.u_total_quantity, apple_qty, "Total quantity should match apple quantity"
        )
        self.assertTrue(pick.u_has_discrepancies, "Pick should have discrepancies")

        # Fulfil 1st move line
        pick.move_line_ids[0].qty_done = apple_qty_per_line

        self.assertEqual(
            pick.u_quantity_done,
            apple_qty_per_line,
            "Quantity done should match apple per line quantity",
        )
        self.assertTrue(pick.u_has_discrepancies, "Pick should have discrepancies")

        # Fulfil 2nd move line which should mean pick is no longer flagged as having discrepancies
        pick.move_line_ids[1].qty_done = apple_qty_per_line

        self.assertEqual(
            pick.u_quantity_done, apple_qty, "Quantity done should match apple quantity"
        )
        self.assertFalse(pick.u_has_discrepancies, "Pick should not have discrepancies")
