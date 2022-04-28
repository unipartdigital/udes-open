from . import common


class TestBackOrder(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestBackOrder, cls).setUpClass()

        # Create two quants in location_01
        cls.create_quant(cls.apple.id, cls.test_location_01.id, 5)
        cls.create_quant(cls.banana.id, cls.test_location_01.id, 5)
        # Create a picking for two different products
        cls.pick1 = cls.create_picking(
            picking_type=cls.picking_type_pick,
            products_info=[
                {"product": cls.apple, "qty": 5},
                {"product": cls.banana, "qty": 5},
            ],
            assign=True,
        )

    def test_requires_backorder_for_incomplete_moves(self):
        """
        Test a picking is flagged as needing a backorder if it has incomplete
        moves.
        """

        # Set qty done to 5 for apple and leave as 0 banana
        apple_move_lines = self.pick1.move_line_ids.filtered(lambda ml: ml.product_id == self.apple)
        apple_move_lines.qty_done = 5

        # Assert that this picking requires a backorder
        self.assertTrue(self.pick1._requires_backorder(apple_move_lines))

    def test_backorder_not_created_for_cancelled_moves(self):
        """
        Test a picking is not flagged as needing a backorder if the remaining incomplete
        moves are cancelled.
        """
        # Set qty done to 5 on apple
        apple_move_lines = self.pick1.move_line_ids.filtered(lambda ml: ml.product_id == self.apple)
        apple_move_lines.qty_done = 5

        # Cancel the banana move
        banana_move = self.pick1.move_lines.filtered(
            lambda ml: ml.product_id == self.banana
        ).ensure_one()
        banana_move._action_cancel()

        # Assert that this picking does not require a backorder
        self.assertFalse(self.pick1._requires_backorder(apple_move_lines))
