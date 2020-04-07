# -*- coding: utf-8 -*-

from . import common
from unittest.mock import patch


class TestStockMove(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestStockMove, cls).setUpClass()
        # Create a picking
        cls._pick_info = [{'product': cls.banana, 'qty': 6}]
        cls.quant1 = cls.create_quant(cls.banana.id, cls.test_stock_location_01.id, 5)
        cls.quant2 = cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 3)
        cls.pick = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True, assign=True
        )

    def test01_split_out_move_lines_raise_error(self):
        """ Raise a value error when try to split out move lines from another move """
        # Create another picking
        new_pick_info = [{'product': self.apple, 'qty': 20}]
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
            str(e.exception), 'Cannot split move lines from a move they are not part of.'
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
            self.env['stock.quant'].search([]).mapped('reserved_quantity'),
        )

    def test04_unreserve_initial_demand(self):
        """ Test for _unreserve_initial_demand """
        MoveLine = self.env['stock.move.line']
        pack1 = self.create_package()
        pack2 = self.create_package()
        self.create_quant(self.fig.id, self.test_stock_location_01.id, 2, package_id=pack1.id)
        self.create_quant(self.fig.id, self.test_stock_location_01.id, 2, package_id=pack2.id)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=[{'product': self.fig, 'qty': 5}],
            location_dest_id=self.test_received_location_01.id,
            location_id=self.test_stock_location_01.id,
            assign=True,
        )
        fig_move = picking.move_lines
        move_lines = fig_move.move_line_ids
        pack1_ml = move_lines.filtered(lambda ml: ml.package_id == pack1)
        pack2_ml = move_lines.filtered(lambda ml: ml.package_id == pack2)

        # Complete pack 1 operation
        pack1_ml.write({'qty_done': 2})
        # fig_move._action_done()
        # Validate picking which will create backorder preserving remaining ml to do
        picking.action_done()
        # Check the move line ids attached to move is still there
        self.assertEqual(pack1_ml, picking.move_line_ids)
        self.assertEqual(pack1_ml.move_id, fig_move)
        # Get the again all the fig move lines, check that they are the same as before
        new_move_lines = MoveLine.search([('product_id', '=', self.fig.id)])
        self.assertEqual(move_lines, new_move_lines)
        self.assertIn(pack2_ml, new_move_lines)
