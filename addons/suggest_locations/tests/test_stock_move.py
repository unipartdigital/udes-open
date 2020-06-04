# -*- coding: utf-8 -*-
from . import common


class TestStockMove(common.SuggestedLocations):
    @classmethod
    def setUpClass(cls):
        super(TestStockMove, cls).setUpClass()
        # Create picking
        cls.create_quant(cls.apple.id, cls.stock_location.id, 100)
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 100)
        cls._pick_info = [{"product": cls.banana, "qty": 5}, {"product": cls.apple, "qty": 4}]
        cls.picking = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True
        )
        cls.moves = cls.picking.move_lines
        # Get apple move
        cls.apple_mv = cls.moves.filtered(lambda mv: mv.product_id == cls.apple)

    def test01_prepare_move_line_vals_no_policy(self):
        """Check that the default location is returned in the dict when no policy is chosen"""
        # Set suggested locations policy
        self.picking_type_pick.u_suggest_locations_policy = None
        # Check first the default location is used in the returned dict
        self.assertEqual(
            self.apple_mv._prepare_move_line_vals().get("location_dest_id"), self.out_location.id,
        )

    def test02_prepare_move_line_vals(self):
        """Check the location_dest_id is a suggested location"""
        # Set suggested locations policy
        self.picking_type_pick.u_suggest_locations_policy = "by_product"
        # Check first the default location is used in the returned dict
        self.assertEqual(
            self.apple_mv._prepare_move_line_vals().get("location_dest_id"), self.out_location.id,
        )
        # Create quant - should now get this as the destination location
        self.create_quant(self.apple.id, self.test_goodsout_location_02.id, 10)
        self.assertEqual(
            self.apple_mv._prepare_move_line_vals().get("location_dest_id"),
            self.test_goodsout_location_02.id,
        )

        self.picking.action_assign()
        apple_mls = self.apple_mv.move_line_ids
        self.assertEqual(apple_mls.location_dest_id, self.test_goodsout_location_02)
