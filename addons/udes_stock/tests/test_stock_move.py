# -*- coding: utf-8 -*-

from . import common
from unittest.mock import patch


class TestStockMove(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockMove, cls).setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.Move = cls.env["stock.move"]

        # Create a picking
        cls._pick_info = [{"product": cls.banana, "qty": 6}]
        cls.quant1 = cls.create_quant(cls.banana.id, cls.test_stock_location_01.id, 5)
        cls.quant2 = cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 3)
        cls.pick = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True, assign=True
        )

    def _get_expected_move_line_values(self, move, qty, **kwargs):
        """ Helper to get expected move line values """
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

    def test01_split_out_move_lines_raise_error(self):
        """ Raise a value error when try to split out move lines from another move """
        # Create another picking
        new_pick_info = [{"product": self.apple, "qty": 20}]
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

    def test02_split_out_move_lines_success(self):
        """ Completely covered by move_lines, expect to be removed from picking
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

    def test03_split_out_move_lines_with_split(self):
        """ Not covered by move_lines, expect to be removed from picking results in splitting
            No chained moves
        """
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
            [self.quant1.reserved_quantity, self.quant2.reserved_quantity],
            self.env["stock.quant"].search([]).mapped("reserved_quantity"),
        )

    def test04_unreserve_initial_demand(self):
        """ Test for _unreserve_initial_demand """
        MoveLine = self.env["stock.move.line"]
        pack1 = self.create_package()
        pack2 = self.create_package()
        self.create_quant(self.fig.id, self.test_stock_location_01.id, 2, package_id=pack1.id)
        self.create_quant(self.fig.id, self.test_stock_location_01.id, 2, package_id=pack2.id)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.fig, "qty": 5}],
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
        picking.action_done()
        # Check the move line ids attached to move is still there
        self.assertEqual(pack1_ml, picking.move_line_ids)
        self.assertEqual(pack1_ml.move_id, fig_move)
        # Get the again all the fig move lines, check that they are the same as before
        new_move_lines = MoveLine.search([("product_id", "=", self.fig.id)])
        self.assertEqual(move_lines, new_move_lines)
        self.assertIn(pack2_ml, new_move_lines)

    def test05_pepare_and_create_single_move_line(self):
        """ Prepare and create a single move line and check values are correct """
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

    def test06_pepare_and_create_multiple_move_lines(self):
        """ Prepare and create a multiple move lines and check values are correct """
        apple_uom_qty = 5
        banana_uom_qty = 2

        # Create quant for apple
        self.create_quant(self.apple.id, self.test_stock_location_01.id, apple_uom_qty)

        products_info = [
            {"product": self.apple, "qty": apple_uom_qty},
            {"product": self.banana, "qty": banana_uom_qty},
        ]

        move_values = self.Picking._prepare_move(self.pick, [products_info])
        moves = self.Picking._create_move(move_values)

        apple_move = moves.filtered(lambda m: m.product_id == self.apple)
        banana_move = moves.filtered(lambda m: m.product_id == self.banana)

        # Check the prepared move_line_values are correct
        moves_info = {
            apple_move: apple_uom_qty,
            banana_move: banana_uom_qty,
        }
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
