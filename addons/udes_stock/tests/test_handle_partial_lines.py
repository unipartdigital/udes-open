"""Tests for the StockPickingType.u_handle_partial_lines flag."""


from . import common


class HandlePartialLinesTestCase(common.BaseUDES):
    def test_does_not_reserve_partially_available_moves_if_enabled(self):
        """When a picking is assigned, only fully available moves are reserved"""
        Picking = self.env["stock.picking"]

        self.picking_type_pick.u_handle_partials = True
        self.picking_type_pick.u_handle_partial_lines = False

        self.create_quant(self.apple.id, self.test_location_01.id, 10)
        self.create_quant(self.banana.id, self.test_location_01.id, 5)
        products = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
        picking = self.create_picking(self.picking_type_pick, products_info=products, confirm=True)

        self.assertEqual(len(picking.move_lines), 2)

        picking.action_assign()

        self.assertEqual(picking.state, "assigned")
        self.assertEqual(len(picking.move_lines), 2)
        self.assertEqual(len(picking.move_line_ids), 1)

        apple_move = picking.move_lines.filtered(lambda l: l.product_id == self.apple)
        banana_move = picking.move_lines.filtered(lambda l: l.product_id == self.banana)
        self.assertEqual(apple_move.state, "assigned")
        self.assertEqual(banana_move.state, "confirmed")

        # Complete picking
        for ml in picking.move_line_ids:
            ml.write({"qty_done": ml.product_uom_qty})
        picking.update_picking(validate=True)

        # Confirm that the available line has been picked
        self.assertEqual(picking.state, "done")
        self.assertEqual(len(picking.move_lines), 1)
        self.assertEqual(picking.move_lines[0], apple_move)

        # Confirm that the partially available line has been backordered
        backorder = Picking.search(
            [("state", "=", "confirmed"), ("picking_type_id", "=", self.picking_type_pick.id)]
        )
        self.assertEqual(len(backorder), 1)
        waiting_moves = backorder.move_lines
        self.assertEqual(len(waiting_moves), 1)
        self.assertEqual(waiting_moves.product_id, self.banana)
        self.assertEqual(waiting_moves.product_uom_qty, 10)
