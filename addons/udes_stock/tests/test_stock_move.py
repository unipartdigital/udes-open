from odoo.exceptions import ValidationError, UserError
from odoo.tools import mute_logger

from . import common


class TestStockMove(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockMove, cls).setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.Move = cls.env["stock.move"]

        # Create a picking
        cls._pick_info = [{"product": cls.banana, "uom_qty": 6}]
        cls.quant1 = cls.create_quant(cls.banana.id, cls.test_stock_location_01.id, 5)
        cls.quant2 = cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 3)
        cls.pick = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True, assign=True
        )

    def _get_expected_move_line_values(self, move, qty, **kwargs):
        """Helper to get expected move line values"""
        expected_move_values = {
            "move_id": move.id,
            "product_id": move.product_id.id,
            "product_uom_id": move.product_id.uom_id.id,
            "product_uom_qty": qty,
            "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
            "picking_id": move.picking_id.id,
        }
        expected_move_values.update(kwargs)
        return expected_move_values

    def test_split_out_move_lines_raise_error(self):
        """Raise a value error when try to split out move lines from another move"""
        # Create another picking
        new_pick_info = [{"product": self.apple, "uom_qty": 20}]
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.apple.id, self.test_stock_location_02.id, 10)
        new_pick = self.create_picking(
            self.picking_type_pick, products_info=new_pick_info, confirm=True, assign=True
        )
        # Get the move lines associated to the new pick, and the move for self.pick
        mls = new_pick.move_line_ids
        mv = self.pick.move_lines
        with self.assertRaises(ValueError) as e:
            mv.split_out_move_lines(mls)
        self.assertEqual(
            str(e.exception), "Cannot split move lines from a move they are not part of."
        )

    def test_split_out_move_lines_success(self):
        """Completely covered by move_lines, expect to be removed from picking
        No chained moves
        """
        # Get move lines and moves respectively
        mls = self.pick.move_line_ids
        mv = self.pick.move_lines
        self.assertEqual(self.pick, mv.picking_id)
        bk_move = mv.split_out_move_lines(mls)
        self.assertFalse(bk_move.picking_id)
        self.assertEqual(bk_move, mv)
        self.assertEqual(mls, bk_move.move_line_ids)
        self.assertEqual(bk_move.product_uom_qty, 6)

    def test_split_out_move_lines_with_split(self):
        """Not covered by move_lines, expect to be removed from picking results in splitting
        No chained moves
        """
        Quant = self.env["stock.quant"]
        # Get all move lines, ones from location 01 and moves respectively
        all_mls = self.pick.move_line_ids
        mls = all_mls.filtered(lambda ml: ml.location_id == self.test_stock_location_01)
        mv = self.pick.move_lines
        self.assertEqual(self.pick, mv.picking_id)
        bk_move = mv.split_out_move_lines(mls)
        # Check the returned move does not have a picking id
        self.assertFalse(bk_move.picking_id)
        # Check state is preserved
        self.assertEqual(mv.state, bk_move.state)
        # Check quantity is correct
        self.assertEqual(bk_move.product_uom_qty, 5)
        # Check mls have the one move id
        self.assertEqual(
            self.pick.move_line_ids,
            all_mls.filtered(lambda ml: ml.location_id == self.test_stock_location_02),
        )
        self.assertEqual(bk_move.move_line_ids, mls)
        # Check that nothing is additionally reserved
        self.assertEqual(
            sum([self.quant1.reserved_quantity, self.quant2.reserved_quantity]),
            sum(Quant.search([]).mapped("reserved_quantity")),
        )

    def test_split_out_incomplete_move_raises_exception_when_qty_done_in_ml_less_than_product_uom_qty(
        self,
    ):
        """
        When trying to split a move, raise an execption if the move line qty > 0 and
        is != product_uom_qty.
        """
        self.pick.move_line_ids.qty_done = 1
        with self.assertRaises(ValidationError) as e, mute_logger("odoo.sql_db"):
            self.pick.move_lines.split_out_incomplete_move()

        # Check the error is as expected
        self.assertEqual(
            e.exception.args[0],
            "You cannot create a backorder for %s with a move line qty less than expected!"
            % self.pick.name,
        )

    def test_split_out_incomplete_move_with_nothing_done(self):
        """
        Test that split_out_incomplete_move returns self when the move
        is not complete, and that the picking info has been removed.
        """
        # Get move lines and moves respectively
        mls = self.pick.move_line_ids
        mv = self.pick.move_lines
        self.assertEqual(self.pick, mv.picking_id)
        new_move = mv.split_out_incomplete_move()
        self.assertEqual(new_move, mv)
        self.assertEqual(new_move.move_line_ids, mls)
        self.assertFalse(new_move.picking_id)
        self.assertFalse(new_move.move_line_ids.picking_id)

    def test_split_out_incomplete_move_with_everything_done(self):
        """
        Test that split_out_incomplete_move returns an empty record when the move
        is fully completed.
        """
        # Get move lines and moves respectively
        mls = self.pick.move_line_ids
        mv = self.pick.move_lines
        self.assertEqual(self.pick, mv.picking_id)
        for ml in mls:
            ml.qty_done = ml.product_uom_qty
        self.assertEqual(mv.quantity_done, mv.product_uom_qty)
        new_move = mv.split_out_incomplete_move()
        self.assertFalse(new_move)

    def test_split_out_incomplete_move_with_subset_of_completed_mls(self):
        """
        Test that when a move line is done, but not the set of move lines
        to complete the move, the move is correctly split, with the done
        mls in the original move and picking.
        """
        # Get move lines and moves respectively
        mls = self.pick.move_line_ids
        mv = self.pick.move_lines
        self.assertEqual(len(mv), 1)
        self.assertEqual(len(mls), 2)
        self.assertEqual(self.pick, mv.picking_id)
        # Update the ml with the min quantity. Do no hard code in case
        # quant selection changes.
        ml_qt_min = mls.sorted(lambda ml: ml.product_uom_qty)[0]
        min_qty = ml_qt_min.product_uom_qty
        ml_qt_min.qty_done = min_qty
        other_ml = mls - ml_qt_min

        # Do the split
        self.assertEqual(mv.quantity_done, min_qty)
        new_move = mv.split_out_incomplete_move()

        # Check we have two moves
        self.assertTrue(self.pick.move_lines)
        self.assertTrue(new_move)

        # Check the original picking move
        self.assertEqual(self.pick.move_lines, mv)
        self.assertEqual(self.pick.move_line_ids, ml_qt_min)
        # Ge the move lines from the pick again to refresh it
        ml = self.pick.move_line_ids
        mv = self.pick.move_lines
        # Check the quants
        self.assertEqual(mv.quantity_done, min_qty)
        self.assertEqual(mv.product_uom_qty, min_qty)
        self.assertEqual(ml.qty_done, min_qty)
        self.assertEqual(ml.product_uom_qty, min_qty)

        # Check the new move
        # Check the quants
        self.assertEqual(new_move.quantity_done, 6 - min_qty)
        self.assertEqual(new_move.product_uom_qty, 6 - min_qty)
        self.assertEqual(new_move.move_line_ids, other_ml)

    def test_split_out_incomplete_move_with_subset_of_completed_mls(self):
        """
        Test that when a move line is done, but not the set of move lines
        to complete the move, the move is correctly split, with the done
        mls in the original move and picking.
        """
        pick_info = [{"product": self.apple, "uom_qty": 10}]
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.apple.id, self.test_stock_location_02.id, 3)
        pick = self.create_picking(self.picking_type_pick, products_info=pick_info, assign=True)
        # Get move lines and moves respectively
        mls = pick.move_line_ids
        mv = pick.move_lines
        self.assertEqual(pick, mv.picking_id)
        self.assertEqual(len(mv), 1)
        self.assertEqual(len(mls), 2)

        ml_qty_3 = mls.filtered(lambda ml: ml.product_uom_qty == 3)
        ml_qty_3.qty_done = 3
        ml_qty_5 = mls.filtered(lambda ml: ml.product_uom_qty == 5)

        # Do the split
        new_move = mv.split_out_incomplete_move()

        # Check the original move has the work done
        self.assertEqual(pick.move_lines, mv)
        self.assertEqual(pick.move_line_ids, ml_qty_3)
        # Sanity check the quants
        mv = pick.move_lines  # Refresh the moves
        mls = pick.move_line_ids  # Refresh the mls
        self.assertEqual(mv.product_uom_qty, 3)
        self.assertEqual(mv.quantity_done, 3)
        self.assertEqual(mls.product_uom_qty, 3)
        self.assertEqual(mls.qty_done, 3)

        # Check the new move has the work pending
        new_mls = new_move.move_line_ids
        self.assertEqual(new_move.product_uom_qty, 7)
        self.assertEqual(new_move.quantity_done, 0)
        self.assertEqual(new_mls, ml_qty_5)
        self.assertEqual(new_mls.product_uom_qty, 5)
        self.assertEqual(new_mls.qty_done, 0)

    def test_unreserve_initial_demand(self):
        """Test for _unreserve_initial_demand"""
        MoveLine = self.env["stock.move.line"]
        pack1 = self.create_package()
        pack2 = self.create_package()
        self.create_quant(self.fig.id, self.test_stock_location_01.id, 2, package_id=pack1.id)
        self.create_quant(self.fig.id, self.test_stock_location_01.id, 2, package_id=pack2.id)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.fig, "uom_qty": 5}],
            location_dest_id=self.test_received_location_01.id,
            location_id=self.test_stock_location_01.id,
            assign=True,
        )
        fig_move = picking.move_lines
        move_lines = fig_move.move_line_ids
        pack1_ml = move_lines.filtered(lambda ml: ml.package_id == pack1)
        pack2_ml = move_lines.filtered(lambda ml: ml.package_id == pack2)

        # Complete pack 1 operation
        pack1_ml.write({"qty_done": 2})
        # fig_move._action_done()
        # Validate picking which will create backorder preserving remaining ml to do
        picking._action_done()
        # Check the move line ids attached to move is still there
        self.assertEqual(pack1_ml, picking.move_line_ids)
        self.assertEqual(pack1_ml.move_id, fig_move)
        # Get the again all the fig move lines, check that they are the same as before
        new_move_lines = MoveLine.search([("product_id", "=", self.fig.id)])
        self.assertEqual(move_lines, new_move_lines)
        self.assertIn(pack2_ml, new_move_lines)

    def test_pepare_and_create_single_move_line(self):
        """Prepare and create a single move line and check values are correct"""
        product_uom_qty = 2

        move_values = self.Picking._prepare_move(self.pick, [self._pick_info])
        move = self.Picking._create_move(move_values)

        # Check the prepared move_line_values are correct
        move_line_values = self.Move._prepare_move_line(move, product_uom_qty)
        self.assertEqual(
            move_line_values, self._get_expected_move_line_values(move, product_uom_qty)
        )

        # Create the move line
        move_line = self.Move._create_move_line(move_line_values)

        # Check that one move line has been created and that the move now contains
        # the created move line
        self.assertEqual(len(move_line), 1)
        self.assertEqual(move.move_line_ids, move_line)

        # Confirm picking and assign the stock
        self.pick.action_confirm()
        self.pick.action_assign()

    def test_pepare_and_create_multiple_move_lines(self):
        """Prepare and create a multiple move lines and check values are correct"""
        apple_uom_qty = 5
        banana_uom_qty = 2

        # Create quant for apple
        self.create_quant(self.apple.id, self.test_stock_location_01.id, apple_uom_qty)

        products_info = [
            {"product": self.apple, "uom_qty": apple_uom_qty},
            {"product": self.banana, "uom_qty": banana_uom_qty},
        ]

        move_values = self.Picking._prepare_move(self.pick, [products_info])
        moves = self.Picking._create_move(move_values)

        apple_move = moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = moves.filtered(lambda m: m.product_id == self.banana)

        # Check the prepared move_line_values are correct
        moves_info = {apple_move: apple_uom_qty, banana_move: banana_uom_qty}
        move_line_values = self.Move._prepare_move_lines(moves_info)

        self.assertEqual(
            move_line_values[0], self._get_expected_move_line_values(apple_move, apple_uom_qty)
        )
        self.assertEqual(
            move_line_values[1], self._get_expected_move_line_values(banana_move, banana_uom_qty)
        )

        # Create the move lines
        move_lines = self.Move._create_move_line(move_line_values)
        apple_move_line = move_lines.filtered(lambda ml: ml.product_id == self.apple)
        banana_move_line = move_lines.filtered(lambda ml: ml.product_id == self.banana)

        # Check that two move lines have been created and that the apple and banana
        # moves now contain the correct move lines that were created
        self.assertEqual(len(move_lines), 2)
        self.assertEqual(apple_move.move_line_ids, apple_move_line)
        self.assertEqual(banana_move.move_line_ids, banana_move_line)

        # Confirm picking and assign the stock
        self.pick.action_confirm()
        self.pick.action_assign()
