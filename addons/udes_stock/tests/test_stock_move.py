from odoo.exceptions import ValidationError
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
            cls.picking_type_pick, products_info=cls._pick_info, assign=True
        )

    def _combine_moves_and_pickings(self, target_picking, moves):
        """
        Helper method to place all the moves into a single picking
        Combine moves where possible.
        """
        old_pickings = moves.picking_id - target_picking
        moves.write({"picking_id": target_picking.id})
        mls = moves.move_line_ids
        if mls:
            mls.write({"picking_id": target_picking.id})

        # Combine the moves by product_id and location_id
        for (_product_id, _location_id), moves_to_merge in target_picking.move_lines.groupby(
            lambda mv: (mv.product_id, mv.location_id)
        ):
            target_move = moves_to_merge[0]
            moves_to_unlink = moves_to_merge - target_move
            if moves_to_unlink:
                total_qty = sum(moves_to_merge.mapped("product_uom_qty"))
                target_move.product_uom_qty = total_qty
                moves_to_merge.move_line_ids.write({"move_id": target_move.id})
                moves_to_unlink.unlink()

        # Unlink no longer needed pickings
        old_pickings.unlink()
        target_picking.action_confirm()
        target_picking.action_assign()
        for move in moves:
            with self.subTest(product=move.product_id.name):
                self.assertIn(move.id, target_picking.move_lines.ids)

    def complete_picking(self, picking, dest_location, dest_package_id=None, **picking_kwargs):
        """
        Complete a picking, assumes no backorder is required and everything can be fulfilled
        in the moves via the move lines.
        """
        mls = picking.move_line_ids
        for ml in mls:
            ml.qty_done = ml.product_uom_qty
            ml.location_dest_id = dest_location.id
        # Put them on a package/pallet
        if dest_package_id:
            mls.result_package_id = dest_package_id
        picking.write({**picking_kwargs, "location_dest_id": dest_location.id})
        _backorder = picking.backorder_move_lines(mls_to_keep=mls)
        picking._action_done()
        self.assertEqual(picking.state, "done")

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

    def _setup_picking(self):
        """
        Add moves to self.pick for bananas and cherries.

        Moves:
            * apple: qty=2, reserved=2, qty_done=2, mls=1
            * banana: qty=6, reserved=6, qty_done=6, mls=2
            * cherry: qty=4, reserved=0, qty_done=0, mls=0

        :return:
            - picking, moves, mls
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 2)
        self.create_move(self.pick, [{"product": self.apple, "uom_qty": 2}])
        self.create_move(self.pick, [{"product": self.cherry, "uom_qty": 4}])
        self.pick.action_assign()

        # Check the state of the picking
        moves = self.pick.move_lines
        mls = self.pick.move_line_ids
        mls.location_dest_id = self.test_goodsout_location_01
        self.assertEqual(len(moves), 3)
        self.assertEqual(len(mls), 3)
        return self.pick, moves, mls

    def test_get_incomplete_moves_returns_the_correct_move_set(self):
        """
        Test that get_incomplete_moves returns only those moves not in
        state cancel or done.
        """
        _picking, moves, _mls = self._setup_picking()

        # Test when nothing complete the record set is the original move
        self.assertEqual(moves.get_incomplete_moves(), moves)

        # Test when complete one move it is not returned
        apple_move = moves.filtered(lambda mv: mv.product_id == self.apple)
        banana_move = moves.filtered(lambda mv: mv.product_id == self.banana)
        apple_move.move_line_ids.qty_done = apple_move.product_uom_qty
        apple_move._action_done()
        self.assertEqual(apple_move.state, "done")
        banana_move._action_cancel()
        self.assertEqual(banana_move.state, "cancel")
        self.assertEqual(moves.get_incomplete_moves(), moves - apple_move - banana_move)

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

    def test_sets_correct_move_quantities_when_splitting_out_done_move_lines(self):
        """When splitting out done move lines, the correct move quantities must be set."""
        MoveLine = self.env["stock.move.line"]

        products_info = [{"product": self.apple, "qty": 3}]
        picking = self.create_picking(
            self.picking_type_goods_in,
            products_info=products_info,
            confirm=True,
            assign=True,
        )
        original_move = picking.move_lines

        # Find / prepare move lines to partially complete.
        product_ids = [{"barcode": self.apple.barcode, "uom_qty": 2}]
        vendor_location = self.env.ref("stock.stock_location_suppliers")
        prepared_mls = picking.move_line_ids.prepare(
            product_ids=product_ids,
            package=None,
            location=vendor_location,
            result_package=self.create_package(),
            location_dest=self.test_received_location_01,
        )
        # Mark move line as done / picked
        mls_done = MoveLine.browse()
        for mls, mls_values in prepared_mls.items():
            mls.mark_as_done(mls_values)
            mls_done |= mls

        # Complete the remaining quantity.
        second_move_line = picking.move_line_ids.filtered(lambda ml: ml.qty_done == 0)
        second_move_line.write(
            {
                "location_dest_id": self.test_received_location_02.id,
                "result_package_id": self.create_package().id,
                "qty_done": 1,
            }
        )

        # Mark the move as done (this will zeroise product_uom_quantity on the
        # move lines).
        original_move._action_done()

        new_move = original_move.split_out_move_lines(move_lines=mls_done)

        moves = original_move | new_move
        self.assertEqual(sorted(moves.mapped("product_uom_qty")), [1, 2])

    def test_split_out_move_raises_exception_when_qty_done_in_ml_less_than_product_uom_qty(
        self,
    ):
        """
        When trying to split a move, raise an execption if the move line qty > 0 and
        is != product_uom_qty.
        """
        self.pick.move_line_ids.qty_done = 1
        with self.assertRaises(ValidationError) as e, mute_logger("odoo.sql_db"):
            self.pick.move_lines.split_out_move()

        # Check the error is as expected
        self.assertEqual(
            e.exception.args[0],
            "There are partially fulfilled move lines in picking %s!" % self.pick.name,
        )

    def test_split_out_move_with_nothing_done(self):
        """
        Test that split_out_move returns self when the move
        is not complete, and that the picking info has been removed.
        """
        # Get move lines and moves respectively
        mls = self.pick.move_line_ids
        mv = self.pick.move_lines
        self.assertEqual(self.pick, mv.picking_id)
        new_move = mv.split_out_move()
        self.assertEqual(new_move, mv)
        self.assertEqual(new_move.move_line_ids, mls)
        self.assertFalse(new_move.picking_id)
        self.assertFalse(new_move.move_line_ids.picking_id)

    def test_split_out_move_with_everything_done(self):
        """
        Test that split_out_move returns an empty record when the move
        is fully completed.
        """
        # Get move lines and moves respectively
        mls = self.pick.move_line_ids
        mv = self.pick.move_lines
        self.assertEqual(self.pick, mv.picking_id)
        for ml in mls:
            ml.qty_done = ml.product_uom_qty
        self.assertEqual(mv.quantity_done, mv.product_uom_qty)
        new_move = mv.split_out_move()
        self.assertFalse(new_move)

    def test_split_out_move_with_subset_of_completed_mls(self):
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
        new_move = mv.split_out_move()

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

    def test_prepare_and_create_single_move_line(self):
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

    def test_prepare_and_create_multiple_move_lines(self):
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

    def test_get_uncovered_moves_returns_empty_record_set_when_fully_covered(self):
        """
        Test that when the mls fully cover the moves an empty record set is returned.
        """
        # Create a picking
        picking, _moves, _mls = self._setup_picking()

        # Create quants to cover the cherry moves
        self.create_quant(self.cherry.id, self.test_stock_location_01.id, 4)
        picking.action_assign()
        self.assertEqual(picking.state, "assigned")

        # Get the relevant moves and mls
        mls = picking.move_line_ids
        moves = picking.move_lines
        apple_move = moves.filtered(lambda mv: mv.product_id == self.apple)
        apple_ml = apple_move.move_line_ids
        self.assertEqual(sum(mls.mapped("product_uom_qty")), sum(moves.mapped("product_uom_qty")))

        # Test no moves returned when fully covered for the whole picking
        self.assertFalse(moves.get_uncovered_moves(mls))

        # Test no moves returned when fully covered for the whole picking
        self.assertFalse(apple_move.get_uncovered_moves(apple_ml))

    def test_get_uncovered_moves_returns_all_moves_if_nothing_covered(self):
        """
        Test that if none of the move lines cover the moves, all the moves are returned
        """
        MoveLine = self.env["stock.move.line"]

        # Create a picking
        _picking, moves, _mls = self._setup_picking()
        empty_mls = MoveLine.browse()

        # Create a goods
        goods_in = self.create_picking(
            self.picking_type_goods_in, [{"product": self.apple, "uom_qty": 2}], assign=True
        )

        # Test all moves are returned against an empty record set
        self.assertEqual(moves.get_uncovered_moves(empty_mls), moves)
        # Test all moves are returned against mls not attached to the moves
        self.assertEqual(moves.get_uncovered_moves(goods_in.move_line_ids), moves)

    def test_get_uncovered_moves_returns_move_if_only_partially_covered(self):
        """
        Test that if none of the move lines cover the moves, all the moves are returned
        """
        # Create a picking
        _picking, moves, mls = self._setup_picking()
        banana_mv = moves.filtered(lambda mv: mv.product_id == self.banana)
        banana_mls = banana_mv.move_line_ids
        self.assertEqual(len(banana_mv), 1)
        self.assertEqual(len(banana_mls), 2)
        banana_3ml = mls.filtered(
            lambda ml: ml.product_id == self.banana and ml.product_uom_qty == 3
        )
        banana_5ml = mls.filtered(
            lambda ml: ml.product_id == self.banana and ml.product_uom_qty == 5
        )

        # Test when called against only the banana move
        self.assertEqual(banana_mv.get_uncovered_moves(banana_3ml), banana_mv)
        self.assertEqual(banana_mv.get_uncovered_moves(banana_5ml), banana_mv)
        # Test when called against all moves in the picking
        self.assertEqual(moves.get_uncovered_moves(banana_3ml), moves)
        self.assertEqual(moves.get_uncovered_moves(banana_5ml), moves)


class TestUdesPropagateCancel(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        """
        Test u_propagate_cancel field is working on at least a 3 pick chain
        """
        super().setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.Move = cls.env["stock.move"]
        cls.package1 = cls.create_package()
        cls.package2 = cls.create_package()
        # Create a picking
        cls._pick_info = [{"product": cls.banana, "uom_qty": 6}]
        cls.quant1 = cls.create_quant(cls.banana.id, cls.test_stock_location_01.id, 5)
        cls.quant2 = cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 3)
        cls.pick = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, assign=True
        )
        cls.pick_ml1 = cls.pick.move_line_ids.filtered(lambda ml: ml.product_qty == 5)
        cls.pick_ml2 = cls.pick.move_line_ids.filtered(lambda ml: ml.product_qty == 1)

        cls.pick_ml1.location_dest_id = cls.test_goodsout_location_01
        cls.pick_ml2.location_dest_id = cls.test_goodsout_location_01

    def toggle_u_propagate_cancel(self, toggle_value):
        """Helper function to enable/disable u_propagate_cancel on all picking types"""
        picking_types_to_configure = [
            self.picking_type_pick,
            self.picking_type_check,
            self.picking_type_goods_out,
            self.picking_type_trailer_dispatch,
        ]
        for picking_type in picking_types_to_configure:
            picking_type.u_propagate_cancel = toggle_value

    def get_next_pick_chain(self, picking):
        StockPicking = self.env["stock.picking"]
        next_pick_chain = StockPicking.browse()
        while picking:
            next_picks = picking.mapped("u_next_picking_ids")
            next_pick_chain |= next_picks
            picking = next_picks
        return next_pick_chain

    def test_cancel_picking_does_not_propagate_to_next_pickings(self):
        """
        If u_propagate_cancel is disabled on all picking types,
        ensure that when a Pick is cancelled, no propagation occurs
        """
        self.toggle_u_propagate_cancel(False)

        self.pick_ml1.result_package_id = self.package1
        self.pick_ml1.qty_done = 5
        self.pick._action_done()
        bk_pick = self.pick.u_created_backorder_ids
        self.assertEqual(bk_pick.move_lines.product_qty, 1)
        next_pickings = self.get_next_pick_chain(bk_pick)
        self.assertTrue(len(next_pickings) == 3)
        for next_picking in next_pickings:
            with self.subTest():
                self.assertEqual(next_picking.move_lines.product_qty, 6)
        bk_pick.action_cancel()
        self.assertEqual(bk_pick.state, "cancel")
        for next_picking in next_pickings:
            with self.subTest():
                self.assertEqual(next_picking.move_lines.product_qty, 6)

    def test_cancel_picking_propagates_to_some_next_pickings(self):
        """
        If u_propagate_cancel is enabled on Pick only,
        ensure that when a Pick is cancelled, propagation only occurs to Check
        """
        self.toggle_u_propagate_cancel(False)
        self.picking_type_pick.u_propagate_cancel = True
        self.pick_ml1.result_package_id = self.package1
        self.pick_ml1.qty_done = 5
        self.pick._action_done()
        bk_pick = self.pick.u_created_backorder_ids
        self.assertEqual(bk_pick.move_lines.product_qty, 1)
        next_pickings = self.get_next_pick_chain(bk_pick)
        self.assertTrue(len(next_pickings) == 3)
        for next_picking in next_pickings:
            with self.subTest():
                self.assertEqual(next_picking.move_lines.product_qty, 6)
        bk_pick.action_cancel()
        self.assertEqual(bk_pick.state, "cancel")
        for next_picking in next_pickings:
            with self.subTest():
                if next_picking.picking_type_id == self.picking_type_check:
                    self.assertEqual(next_picking.move_lines.product_qty, 5)
                else:
                    self.assertEqual(next_picking.move_lines.product_qty, 6)

    def test_cancel_picking_propagates_to_next_pickings(self):
        """
        If u_propagate_cancel is enabled on all picking types,
        ensure that when a Pick is cancelled, the moves (and pickings)
        down the chain are all cancelled.
        """
        self.toggle_u_propagate_cancel(True)

        next_pickings = self.get_next_pick_chain(self.pick)
        self.assertTrue(len(next_pickings) == 3)
        for next_picking in next_pickings:
            with self.subTest():
                self.assertEqual(next_picking.move_lines.product_qty, 6)
        self.pick.action_cancel()
        self.assertEqual(self.pick.state, "cancel")
        for next_picking in next_pickings:
            with self.subTest():
                self.assertEqual(next_picking.state, "cancel")

    def test_cancel_picking_backorder_propagates_to_next_pickings(self):
        """
        If u_propagate_cancel is enabled on all picking types,
        ensure that when a Pick is partially processed (and a backorder is created),
        the moves on the backorder propagate their cancellation (by means of deducting qty)
        all the way down the chain
        """
        self.toggle_u_propagate_cancel(True)
        self.pick_ml1.result_package_id = self.package1
        self.pick_ml1.qty_done = 5
        self.pick._action_done()
        bk_pick = self.pick.u_created_backorder_ids
        self.assertEqual(bk_pick.move_lines.product_qty, 1)
        next_pickings = self.get_next_pick_chain(bk_pick)
        self.assertTrue(len(next_pickings) == 3)
        for next_picking in next_pickings:
            with self.subTest():
                self.assertEqual(next_picking.move_lines.product_qty, 6)
        bk_pick.action_cancel()
        self.assertEqual(bk_pick.state, "cancel")
        for next_picking in next_pickings:
            with self.subTest():
                self.assertEqual(next_picking.move_lines.product_qty, 5)


class TestUpdateOrigIds(TestStockMove):
    """
    This test class is used to check that the orig_move_ids are correctly
    propagated and set through chained pickings.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Define the stock move logger
        cls.logger = "odoo.addons.udes_stock.models.stock_move"

    def test_update_orig_ids_with_product_location_default_matching(self):
        """
        Test that update_orig_ids updates the origins for the moves corectly and the pickings
        always point to the relevant original moves, when pickings are chained. (Pick -> Check)
        Here the matching is based on the product and the current location id and the previous
        move lines destination id.

        Setup:
            * Begin with single picking one move, two move lines.
            * Complete 1 move line, drop off pick in dest location 01
            * Complete backorder and drop off pick in dest location 02
            * Complete the move lines in the out picking
            * Assert that the move lines get mapped to the correct original move
        """
        original_banana_move = self.pick.move_lines
        banana_1ml = self.pick.move_line_ids.filtered(lambda ml: ml.product_uom_qty == 1)
        backorder = self.pick.backorder_move_lines(banana_1ml)
        self.complete_picking(self.pick, self.test_check_location_01)

        # Add the newly created backorder move
        backorder_banana_move = backorder.move_lines

        # Complete the backorder and drop in a different location
        self.complete_picking(backorder, self.test_check_location_02)

        # Next pickings: Get the outbound picking
        out_picking = self.Picking.search(
            [("state", "=", "assigned"), ("picking_type_id", "=", self.picking_type_check.id)]
        )
        self.assertEqual(len(out_picking), 1)
        self.assertEqual(len(out_picking.move_line_ids), 2)

        # Check that the next picking contains all references to the original move information
        self.assertEqual(
            out_picking.move_lines.move_orig_ids, original_banana_move | backorder_banana_move
        )

        # Backorder and complete the outbound pickings by move line
        # Complete the banana move with 5 in it first (reverse of before)
        out_banana_5ml = out_picking.move_line_ids.filtered(lambda ml: ml.product_uom_qty == 5)
        self.assertEqual(len(out_banana_5ml), 1)

        # Assert no Warning logs occur in later unittest version 3.10
        # Instead tested via inspection :)
        # with self.assertNoLogs(self.logger, level="WARNING"):
        #     backorder_out1 = out_picking.backorder_move_lines(mls_to_keep=out_banana_5ml)

        backorder_out1 = out_picking.backorder_move_lines(mls_to_keep=out_banana_5ml)
        self.complete_picking(out_picking, self.test_trailer_location_01)
        self.assertEqual(out_picking.move_lines.move_orig_ids, backorder_banana_move)

        # Recheck the state is as expected
        self.assertEqual(out_picking.move_lines.move_orig_ids, backorder_banana_move)
        self.assertEqual(backorder_out1.move_lines.move_orig_ids, original_banana_move)

    def test_update_orig_ids_by_package_or_lot_or_both(self):
        """
        Test that update_orig_ids updates the origins for the moves corectly and the pickings
        always point to the relevant original moves.

        Setup:
            * Begin with one picking:
                Banana 1 moves, 2ml, no tracking
                Apple 1 moves, 3ml, tracking
            * Complete partial amount of picking one onto one package, banana ml of qty 1
            * Complete lot tracked apple (1 ml) with no package, apple ml of qty 4
            * Complete the final backorder onto another package, all other moves/move lines
            * Check the next step in the process points to all the moves of the previous
            picking type.
            * Complete each picking sequentially matching the move lines as before,
            checking that the orignal picking ids get updated with the correct move lines.

        The apples are matched by package and lot or just lot, the bananas are matched by package only.
        """
        # Create packages
        package1 = self.create_package()
        package2 = self.create_package()

        # Add a apple move with lots for all three quants
        # Test the state of the picking and store some lot information
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 1, lot_name="TestApple1")
        apple_q2 = self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 1, lot_name="TestApple2"
        )
        lot2 = apple_q2.lot_id
        apple_q3 = self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, lot_name="TestApple3"
        )
        lot3 = apple_q3.lot_id
        apple_move = self.create_move(self.pick, [{"product": self.apple, "uom_qty": 6}])
        self.pick.action_assign()
        self.assertEqual(len(self.pick.move_lines), 2)
        self.assertEqual(len(self.pick.move_line_ids), 5)
        self.assertEqual(self.pick.move_lines.product_id, self.apple | self.banana)
        self.assertEqual(self.pick.state, "assigned")

        # Pick one move line and backorder the rest
        mls = self.pick.move_line_ids
        apple_ml4 = apple_move.move_line_ids.filtered(lambda ml: ml.product_uom_qty == 4)
        banana_1ml = mls.filtered(
            lambda ml: ml.product_uom_qty == 1 and ml.product_id == self.banana
        )
        orig_banana_move = banana_1ml.move_id

        # Add the backorder moves to the orignal moves record set
        backorder1 = self.pick.backorder_move_lines(mls_to_keep=banana_1ml)
        backorder2 = backorder1.backorder_move_lines(mls_to_keep=apple_ml4)
        back2_apple_move = backorder2.move_lines.filtered(lambda ml: ml.product_id == self.apple)
        back2_banana_move = backorder2.move_lines.filtered(lambda ml: ml.product_id == self.banana)

        # Assign the destination packages
        # Assign a package to the first banana picking
        # Do not assign for backorder1
        # Assign a package to backorder2
        self.pick.move_line_ids.result_package_id = package1.id
        backorder2.move_line_ids.write({"result_package_id": package2.id})

        # Complete the original picking, then the backorders, and drop in the same location
        self.complete_picking(self.pick, self.test_check_location_01)
        self.complete_picking(backorder1, self.test_check_location_01)
        self.complete_picking(backorder2, self.test_check_location_01)

        # Next pickings: Get the outbound picking
        out_picking = self.Picking.search(
            [("state", "=", "assigned"), ("picking_type_id", "=", self.picking_type_check.id)]
        )
        self.assertEqual(len(out_picking), 1)
        self.assertEqual(len(out_picking.move_lines), 2)
        self.assertEqual(len(out_picking.move_line_ids), 5)

        # Check that the next picking contains all references to the original move information
        self.assertEqual(
            out_picking.move_lines.move_orig_ids,
            orig_banana_move | apple_move | back2_apple_move | back2_banana_move,
        )

        # Backorder and complete the outbound pickings first lot then package by package
        # Complete apple move line (lot tracked) with lot3, no package
        apple_out_4ml = out_picking.move_line_ids.filtered(lambda ml: ml.lot_id == lot3)
        self.assertEqual(len(apple_out_4ml), 1)
        self.assertEqual(apple_out_4ml.product_uom_qty, 4)
        # Have to create package for the apples
        apple_out_4ml.result_package_id = self.create_package()
        backorder_out1 = out_picking.backorder_move_lines(mls_to_keep=apple_out_4ml)
        self.complete_picking(out_picking, self.test_goodsout_location_01)
        self.assertEqual(out_picking.move_lines.move_orig_ids, apple_move)

        # Complete another apple move line with lot2, can be identified by package and lot
        apple_out_1ml = backorder_out1.move_line_ids.filtered(lambda ml: ml.lot_id == lot2)
        self.assertEqual(len(apple_out_1ml), 1)
        # Have to create package for the apples
        apple_out_1ml.result_package_id = self.create_package()
        backorder_out2 = backorder_out1.backorder_move_lines(mls_to_keep=apple_out_1ml)
        self.complete_picking(backorder_out1, self.test_goodsout_location_01)
        self.assertEqual(backorder_out1.move_lines.move_orig_ids, back2_apple_move)

        # Complete the remaining parts of the second package first (switcheroo)
        # Banana and apple. The banana is matched by package, the apple by lot and package
        package2_mls = backorder_out2.move_line_ids.filtered(lambda ml: ml.package_id == package2)
        backorder_out3 = backorder_out2.backorder_move_lines(mls_to_keep=package2_mls)
        self.complete_picking(backorder_out2, self.test_goodsout_location_01)
        self.assertEqual(
            backorder_out2.move_lines.move_orig_ids, back2_apple_move | back2_banana_move
        )

        # Complete the first package, identified by package only
        self.complete_picking(backorder_out3, self.test_goodsout_location_01)
        self.assertEqual(backorder_out3.move_lines.move_orig_ids, orig_banana_move)

        # Recheck the state is as expected
        self.assertEqual(out_picking.move_lines.move_orig_ids, apple_move)
        self.assertEqual(backorder_out1.move_lines.move_orig_ids, back2_apple_move)
        self.assertEqual(
            backorder_out2.move_lines.move_orig_ids, back2_apple_move | back2_banana_move
        )
        self.assertEqual(backorder_out3.move_lines.move_orig_ids, orig_banana_move)

    def test_update_orig_ids_with_partial_availability(self):
        """
        Test that when some of the first picking type moves are not yet avilable,
        they are correctly referenced in the following steps move.orig_move_ids.
        """
        # Setup the picking with apples, bananas and cherries, with the latter unavilable
        picking, original_moves, mls = self._setup_picking()
        self.create_quant(self.cherry.id, self.test_stock_location_01.id, 2, lot_name="TEST_LOT")

        # Store the original moves
        apple_move = original_moves.filtered(lambda mv: mv.product_id == self.apple)
        banana_move = original_moves.filtered(lambda mv: mv.product_id == self.banana)
        cherry_move = original_moves.filtered(lambda mv: mv.product_id == self.cherry)
        banana_mls = banana_move.move_line_ids
        self.assertEqual(len(banana_mls), 2)
        banana_1ml = banana_mls.filtered(
            lambda ml: ml.product_id == self.banana and ml.product_uom_qty == 1
        )

        # Complete one banana move line
        banana_1ml.qty_done = banana_1ml.product_uom_qty
        backorder = picking.backorder_move_lines(mls_to_keep=banana_1ml)
        self.complete_picking(picking, self.test_check_location_01)

        # Add the split banana 5 move
        banana_5mv = backorder.move_lines.filtered(lambda mv: mv.product_id == self.banana)
        original_moves |= banana_5mv

        # Split again leaving only unavailable work
        backorder2 = backorder.backorder_move_lines(mls_to_keep=backorder.move_line_ids)
        self.complete_picking(backorder, self.test_check_location_01)
        self.assertEqual(backorder2.state, "confirmed")

        # Add the new remaining move
        incomplete_cherry_move = backorder2.move_lines
        original_moves |= incomplete_cherry_move

        # Next pickings: Get the outbound picking
        out_picking = self.Picking.search(
            [("move_lines", "!=", False), ("picking_type_id", "=", self.picking_type_check.id)]
        )
        self.assertEqual(len(out_picking), 1)

        # Check that the next picking contains all references to the original move information
        self.assertEqual(out_picking.move_lines.move_orig_ids, original_moves)

        # Backorder and complete the outbound pickings move by move
        # Complete the apples
        apple_mls = out_picking.move_line_ids.filtered(lambda ml: ml.product_id == self.apple)
        backorder_out1 = out_picking.backorder_move_lines(mls_to_keep=apple_mls)
        self.complete_picking(out_picking, self.test_trailer_location_01)
        self.assertEqual(out_picking.move_lines.move_orig_ids, apple_move)

        # Complete the banana moves
        remaining_banana_mls = backorder_out1.move_line_ids.filtered(
            lambda ml: ml.product_id == self.banana
        )
        backorder_out3 = backorder_out1.backorder_move_lines(mls_to_keep=remaining_banana_mls)
        self.complete_picking(backorder_out1, self.test_goodsout_location_01)
        self.assertEqual(backorder_out1.move_lines.move_orig_ids, banana_move | banana_5mv)

        # Check the state is as expected. The out picking with just apple move points to the
        # orignal apple move etc. For any incomplete work, they remain in the picking that is
        # not yet complete (i.e the cherries here)
        self.assertEqual(out_picking.move_lines.move_orig_ids, apple_move)
        self.assertEqual(backorder_out1.move_lines.move_orig_ids, banana_move | banana_5mv)
        self.assertEqual(
            backorder_out3.move_lines.move_orig_ids, cherry_move | incomplete_cherry_move
        )

    def test_update_orig_ids_over_matches_by_product_and_location(self):
        """
        Create two identical pickings, complete them, then split the out move into two which
        over covers the original moves.
        The matcher cannot distinguish between the two move lines to get the oriignal
        move id, so matches both.
        This is an example why we need to avoid default behaviour of _make_mls_comparison_lambda
        in stock.move. Check the logs raise a warning when over matching occurs.
        """
        # Create an additional picking identical to self.pick and complete them both
        product_info = [{"product": self.banana, "uom_qty": 6}]
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 3)
        pick1 = self.pick
        pick2 = self.create_picking(self.picking_type_pick, products_info=product_info, assign=True)
        move1 = pick1.move_lines
        move2 = pick2.move_lines
        self.complete_picking(pick1, self.test_check_location_01)
        self.complete_picking(pick2, self.test_check_location_01)

        # Check that there is not a mysterious package/lot anywhere
        self.assertFalse(pick1.move_line_ids.result_package_id)
        self.assertFalse(pick2.move_line_ids.result_package_id)
        self.assertFalse(pick1.move_line_ids.lot_id)
        self.assertFalse(pick2.move_line_ids.lot_id)

        # Next pickings: Get the outbound pickings and merge into one, merging moves where possible
        # as well
        out_pickings = self.Picking.search(
            [("state", "=", "assigned"), ("picking_type_id", "=", self.picking_type_check.id)]
        )
        out_picking = out_pickings[0]
        self._combine_moves_and_pickings(
            out_picking, out_pickings.move_lines.filtered(lambda mv: mv.product_id == self.apple)
        )
        self.assertEqual(len(out_picking), 1)
        self.assertEqual(out_picking.move_lines.product_uom_qty, 12)

        # Check that the next picking contains all references to the original move information
        self.assertEqual(out_picking.move_lines.move_orig_ids, move1 | move2)

        # Complete one item of the move line, by splittting it then backordering it.
        out_ml = out_picking.move_line_ids
        new_ml = out_ml._split(1)

        # Check the logs raise a warning message. Note there are two as both self
        # and the backorder picking are updated.
        logger = "odoo.addons.udes_stock.models.stock_move"
        with self.assertLogs(logger, level="WARNING") as cm:
            back_out_picking = out_picking.backorder_move_lines(mls_to_keep=new_ml)
            self.assertEqual(
                cm.output,
                2
                * [
                    f"WARNING:{logger}:"
                    f"""
                    Move lines are being matched by location destination and
                    product, this has lead to over matching of the original move ids.
                    Relevant moves: {( move1 | move2).ids}
                    """
                ],
            )

        # Complete the picking and check the original move ids
        self.complete_picking(out_picking, self.test_trailer_location_01)
        self.assertEqual(out_picking.move_lines.move_orig_ids, move1 | move2)
        self.assertEqual(back_out_picking.move_lines.move_orig_ids, move1 | move2)

    def test_update_orig_ids_over_earlier_backorder_in_chain(self):
        """
        Create a pick and partially complete it. Then with the stock that has been dropped off
        from the pick, complete Check pick for the available stock.

        Ensure that the backorder created for the Check is pointing to the backorder created
        for the previous pick.

        Complete the backorder of the pick and check that the backordered Check has been
        assigned stock.
        """
        # Cancel existing picking, start with
        self.pick.action_cancel()
        products_info = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.cherry, "uom_qty": 8},
            {"product": self.damson, "uom_qty": 3},
        ]
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 10)
        self.create_quant(self.cherry.id, self.test_stock_location_01.id, 8)
        self.create_quant(self.damson.id, self.test_stock_location_01.id, 3)

        pick = self.create_picking(self.picking_type_pick, products_info=products_info, assign=True)

        pallet1 = self.create_package()
        pick.move_line_ids.result_package_id = pallet1
        pick.move_line_ids.location_dest_id = self.test_check_location_01

        # Partially pick apple and cherry lines, fully pick damson line
        pick.move_line_ids.filtered(lambda ml: ml.product_id == self.apple).qty_done = 9
        pick.move_line_ids.filtered(lambda ml: ml.product_id == self.cherry).qty_done = 4
        pick.move_line_ids.filtered(lambda ml: ml.product_id == self.damson).qty_done = 3

        # Partially complete pick
        pick._action_done()
        pick_backorder = pick.backorder_ids

        # Partially complete Check with whatever was completed in Pick
        check = pick.u_next_picking_ids
        self.complete_picking(check, self.test_goodsout_location_01)
        check_backorder = check.backorder_ids
        self.assertEqual(
            check_backorder.u_prev_picking_ids,
            pick_backorder,
            "Check backorder should be pointing to Pick backorder",
        )

        # Complete pick backorder onto a new pallet
        pallet2 = self.create_package()
        self.complete_picking(
            pick_backorder, self.test_check_location_01, dest_package_id=pallet2
        )

        # As the pick backorder has been completed, the Check picking should now be ready
        self.assertEqual(
            check_backorder.state,
            "assigned",
            "Check backorder should be assigned stock after Pick backorder is completed",
        )


class TestFragmentedOriginalMoves(common.BaseUDES):
    """Test case(s) for when a move has more than one original move id."""

    # This is separate from TestUpdateOrigIds because that class inherits a
    # picking chain from TestStockMove that interferes with this test case.

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Picking = cls.env["stock.picking"]

    def test_preserves_multiple_original_moves_in_split(self):
        """Preserves original moves if a move with multiple original moves is split."""
        # Setup

        # Create a pick picking and backorder it repeatedly to create original
        # moves.
        picking_sequence = [3, 2, 2, 2, 1]
        split_qty = 3
        total_quantity = sum(picking_sequence)
        self.create_quant(self.apple.id, self.test_stock_location_01.id, total_quantity)
        udes1, *_ = packages = [
            self.create_package(name=f"UDES{i}") for i in range(1, len(picking_sequence) + 1)
        ]
        products_info = [{"product": self.apple, "qty": total_quantity}]

        picking = self.create_picking(
            self.picking_type_pick, products_info=products_info, assign=True
        )

        pick_pickings = self.Picking.browse()
        for package, quantity in zip(packages, picking_sequence):
            pick_pickings |= picking
            picking.move_line_ids.ensure_one()
            picking.move_line_ids.write(
                {
                    "qty_done": quantity,
                    "result_package_id": package,
                    "location_dest_id": self.test_check_location_01.id,
                }
            )
            picking.move_line_ids._split()
            new_picking = picking.validate_picking(create_backorder=True)
            picking = new_picking

        qty3_pick_move = pick_pickings.mapped("move_lines").filtered(
            lambda m: m.product_uom_qty == split_qty
        )

        check_picking = pick_pickings.mapped("u_next_picking_ids")
        check_picking.ensure_one()

        # We need to engineer a situation where our move has only a single move
        # line, for the quantity that we want to split out,
        check_picking.do_unreserve()

        check_picking.move_lines._update_reserved_quantity(
            total_quantity, split_qty, self.test_check_location_01, package_id=udes1, strict=False
        )
        check_picking.move_lines.state = "partially_available"
        check_picking._check_entire_pack()

        self.assertEqual(len(check_picking.move_lines), 1)
        self.assertEqual(check_picking.move_line_ids.product_uom_qty, split_qty)

        original_check_move = check_picking.move_lines

        # Test: split out a qty 3 move from our picking's move.
        mls_to_split = check_picking.move_line_ids.filtered(
            lambda ml: ml.product_uom_qty == split_qty
        )
        new_check_move = original_check_move.split_out_move_lines(move_lines=mls_to_split)

        # Check that quantities are correct and each move has the expected
        # original move ids.
        self.assertEqual(original_check_move.product_uom_qty, total_quantity - split_qty)
        self.assertEqual(new_check_move.product_uom_qty, split_qty)
        self.assertEqual(
            original_check_move.move_orig_ids, pick_pickings.mapped("move_lines") - qty3_pick_move
        )
        self.assertEqual(new_check_move.move_orig_ids, qty3_pick_move)
