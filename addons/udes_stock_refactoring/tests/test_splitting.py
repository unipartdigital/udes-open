# -*- coding: utf-8 -*-

from addons.udes_stock.tests import common


class TestAssignSplitting(common.BaseUDES):
    def setUp(self):
        """
        Create stock: pallet with apples, pallet with bananas
        create picking: for all of both
        """
        super(TestAssignSplitting, self).setUp()

        # group by package post assign
        self.picking_type_pick.write(
            {
                "u_post_assign_action": "group_by_move_line_key",
                "u_move_line_key_format": "{package_id.name}",
            }
        )

        self.picking = self.create_picking(self.picking_type_pick)

    def test_reserve_one_pallet_per_product_split(self):
        """
        Reserve self.picking with one pallet of each product and check it
        splits correctly when reserved.
        """
        apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=apple_pallet.id
        )

        banana_pallet = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 10, package_id=banana_pallet.id
        )

        products_info = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
        moves = self.create_move(self.picking, products_info)

        apple_move = moves[0]
        banana_move = moves[1]

        self.picking.action_assign()

        apple_pick = apple_move.picking_id
        banana_pick = banana_move.picking_id

        self.assertEqual(apple_pick.state, "assigned")
        self.assertEqual(banana_pick.state, "assigned")
        self.assertEqual(apple_pick.group_id.name, apple_pallet.name)
        self.assertEqual(banana_pick.group_id.name, banana_pallet.name)

        # Check we haven't mangled the moves or move_lines
        apple_move = apple_pick.move_lines
        self.assertEqual(len(apple_move), 1)
        self.assertEqual(apple_move.product_uom_qty, 10)

        apple_move_line = apple_pick.move_line_ids
        self.assertEqual(len(apple_move_line), 1)
        self.assertEqual(apple_move_line.product_qty, 10)
        self.assertEqual(apple_move_line.package_id, apple_pallet)
        self.assertEqual(apple_move_line.result_package_id, apple_pallet)
        self.assertEqual(apple_move_line.product_id, self.apple)

        banana_move = banana_pick.move_lines
        self.assertEqual(len(banana_move), 1)
        self.assertEqual(banana_move.product_uom_qty, 10)

        banana_move_line = banana_pick.move_line_ids
        self.assertEqual(len(banana_move_line), 1)
        self.assertEqual(banana_move_line.product_qty, 10)
        self.assertEqual(banana_move_line.package_id, banana_pallet)
        self.assertEqual(banana_move_line.result_package_id, banana_pallet)
        self.assertEqual(banana_move_line.product_id, self.banana)

        # Check that the original picking has been reused
        self.assertTrue(self.picking.exists())

    def test_split_move(self):
        """
        Reserve self.picking with two pallet of the same product and check it
        splits correctly when reserved.
        """
        MoveLine = self.env["stock.move.line"]

        cherry_pallet1 = self.create_package()
        self.create_quant(
            self.cherry.id, self.test_stock_location_01.id, 10, package_id=cherry_pallet1.id
        )
        cherry_pallet2 = self.create_package()
        self.create_quant(
            self.cherry.id, self.test_stock_location_01.id, 10, package_id=cherry_pallet2.id
        )

        products_info = [{"product": self.cherry, "qty": 20}]
        self.create_move(self.picking, products_info)

        self.picking.action_assign()

        cherry_pallet_move_lines = MoveLine.search(
            [("product_id.name", "=", "Test product Cherry")]
        )

        cherry_pallet1_move_line = False
        cherry_pallet2_move_line = False

        for move_line in cherry_pallet_move_lines:
            if move_line.package_id.name == cherry_pallet1.name:
                cherry_pallet1_move_line = move_line
            elif move_line.package_id.name == cherry_pallet2.name:
                cherry_pallet2_move_line = move_line

        self.assertTrue(cherry_pallet1_move_line)
        self.assertTrue(cherry_pallet2_move_line)

        pick1 = cherry_pallet1_move_line.picking_id
        pick2 = cherry_pallet2_move_line.picking_id

        self.assertEqual(pick1.state, "assigned")
        self.assertEqual(pick2.state, "assigned")
        self.assertEqual(pick1.group_id.name, cherry_pallet1.name)
        self.assertEqual(pick2.group_id.name, cherry_pallet2.name)

        # Check we haven't mangled the moves or move_lines
        pick1_move = pick1.move_lines
        self.assertEqual(len(pick1_move), 1)
        self.assertEqual(pick1_move.product_uom_qty, 10)

        pick1_move_line = pick1.move_line_ids
        self.assertEqual(len(pick1_move_line), 1)
        self.assertEqual(pick1_move_line.product_qty, 10)
        self.assertEqual(pick1_move_line.package_id, cherry_pallet1)
        self.assertEqual(pick1_move_line.result_package_id, cherry_pallet1)
        self.assertEqual(pick1_move_line.product_id, self.cherry)

        pick2_move = pick2.move_lines
        self.assertEqual(len(pick2_move), 1)
        self.assertEqual(pick2_move.product_uom_qty, 10)

        pick2_move_line = pick2.move_line_ids
        self.assertEqual(len(pick2_move_line), 1)
        self.assertEqual(pick2_move_line.product_qty, 10)
        self.assertEqual(pick2_move_line.package_id, cherry_pallet2)
        self.assertEqual(pick2_move_line.result_package_id, cherry_pallet2)
        self.assertEqual(pick2_move_line.product_id, self.cherry)

        # Check that the original picking has been reused
        self.assertTrue(self.picking.exists())

    def test_split_pallet_different_products(self):
        """
        Reserve self.picking with a pallet containing two different products
        and check it splits correctly when reserved.
        """
        mixed_pallet = self.create_package()

        self.create_quant(
            self.fig.id, self.test_stock_location_01.id, 5, package_id=mixed_pallet.id
        )
        self.create_quant(
            self.grape.id, self.test_stock_location_01.id, 10, package_id=mixed_pallet.id
        )

        products_info = [{"product": self.fig, "qty": 5}, {"product": self.grape, "qty": 10}]
        moves = self.create_move(self.picking, products_info)

        fig_move = moves[0]
        grape_move = moves[1]

        self.picking.action_assign()

        pick = (fig_move | grape_move).picking_id

        self.assertEqual(len(pick), 1)
        self.assertEqual(pick.state, "assigned")
        self.assertEqual(pick.group_id.name, mixed_pallet.name)

        # Check we haven't mangled the moves or move_lines
        moves = pick.move_lines
        self.assertEqual(len(moves), 2)

        fig_move = moves.filtered(lambda m: m.product_id == self.fig)
        self.assertEqual(fig_move.product_uom_qty, 5)

        grape_move = moves.filtered(lambda m: m.product_id == self.grape)
        self.assertEqual(grape_move.product_uom_qty, 10)

        move_lines = pick.move_line_ids
        self.assertEqual(len(move_lines), 2)

        fig_moveline = move_lines.filtered(lambda ml: ml.product_id == self.fig)
        self.assertEqual(fig_moveline.product_qty, 5)
        self.assertEqual(fig_moveline.package_id, mixed_pallet)
        self.assertEqual(fig_moveline.result_package_id, mixed_pallet)

        grape_moveline = move_lines.filtered(lambda ml: ml.product_id == self.grape)
        self.assertEqual(grape_moveline.product_qty, 10)
        self.assertEqual(grape_moveline.package_id, mixed_pallet)
        self.assertEqual(grape_moveline.result_package_id, mixed_pallet)

        # Check that the original picking has been reused
        self.assertTrue(self.picking.exists())

    def test_combine_pickings_at_reserve(self):
        """
        Create two pickings for two items on the same pallet. Reserve them
        simultaneously and check they result in one picking with two moves.
        """
        pallet = self.create_package()

        self.create_quant(
            self.elderberry.id, self.test_stock_location_01.id, 5, package_id=pallet.id
        )
        self.create_quant(
            self.elderberry.id, self.test_stock_location_01.id, 10, package_id=pallet.id
        )

        pick1 = self.picking
        pick2 = self.create_picking(self.picking_type_pick)

        pick1_products_info = [{"product": self.elderberry, "qty": 5}]
        move1 = self.create_move(pick1, pick1_products_info)

        pick2_products_info = [{"product": self.elderberry, "qty": 10}]
        move2 = self.create_move(pick2, pick2_products_info)

        (pick1 | pick2).action_assign()

        pick = (move1 | move2).picking_id

        self.assertEqual(len(pick), 1)
        self.assertEqual(pick.state, "assigned")
        self.assertEqual(pick.group_id.name, pallet.name)

        # Check we haven't mangled the moves or move_lines
        self.assertEqual((move1 | move2).ids, pick.move_lines.ids)

        move_lines = pick.move_line_ids
        self.assertEqual(len(move_lines), 2)

        move_line1 = move_lines.filtered(lambda ml: ml.move_id == move1)
        self.assertEqual(move_line1.product_qty, 5)
        self.assertEqual(move_line1.package_id, pallet)
        self.assertEqual(move_line1.product_id, self.elderberry)

        move_line2 = move_lines.filtered(lambda ml: ml.move_id == move2)
        self.assertEqual(move_line2.product_qty, 10)
        self.assertEqual(move_line2.package_id, pallet)
        self.assertEqual(move_line2.product_id, self.elderberry)

        # Check that neither picking has been reused, empty pickings have been
        # marked (u_mark = False) and deleted at the very end of the action
        self.assertFalse(pick1.exists())
        self.assertFalse(pick2.exists())

    def test_items_added_to_existing_picking(self):
        """
        Create two pickings for two items on the same pallet. Reserve them
        sequentially and check they result in one picking with two moves.
        """
        pallet = self.create_package()

        self.create_quant(
            self.elderberry.id, self.test_stock_location_01.id, 5, package_id=pallet.id
        )
        self.create_quant(
            self.elderberry.id, self.test_stock_location_01.id, 10, package_id=pallet.id
        )

        pick1 = self.picking
        pick2 = self.create_picking(self.picking_type_pick)

        pick1_products_info = [{"product": self.elderberry, "qty": 5}]
        move1 = self.create_move(pick1, pick1_products_info)

        pick2_products_info = [{"product": self.elderberry, "qty": 10}]
        move2 = self.create_move(pick2, pick2_products_info)

        pick1.action_assign()
        pick2.action_assign()

        pick = (move1 | move2).picking_id

        self.assertEqual(len(pick), 1)
        self.assertEqual(pick.state, "assigned")
        self.assertEqual(pick.group_id.name, pallet.name)

        # Check we haven't mangled the moves or move_lines
        self.assertEqual((move1 | move2).ids, pick.move_lines.ids)

        move_lines = pick.move_line_ids
        self.assertEqual(len(move_lines), 2)

        move_line1 = move_lines.filtered(lambda ml: ml.move_id == move1)
        self.assertEqual(move_line1.product_qty, 5)
        self.assertEqual(move_line1.package_id, pallet)
        self.assertEqual(move_line1.product_id, self.elderberry)

        move_line2 = move_lines.filtered(lambda ml: ml.move_id == move2)
        self.assertEqual(move_line2.product_qty, 10)
        self.assertEqual(move_line2.package_id, pallet)
        self.assertEqual(move_line2.product_id, self.elderberry)

        # Check that the first picking has been reused and the second picking
        # has been marked as empty (u_mark = False) and deleted at the very end
        # of the action
        self.assertTrue(pick1.exists())
        self.assertFalse(pick2.exists())

    def test_check_non_default_locations_maintained(self):
        """
        Reserve when the locations of the picking are not the defaults of
        the picking type and check the non-defaults are maintained.
        """
        self.picking.write(
            {
                "location_id": self.test_stock_location_01.id,
                "location_dest_id": self.test_goodsout_location_01.id,
            }
        )

        apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=apple_pallet.id
        )

        products_info = [{"product": self.apple, "qty": 10}]
        apple_move = self.create_move(self.picking, products_info)

        self.picking.action_assign()

        apple_pick = apple_move.picking_id
        self.assertEqual(self.picking, apple_pick)  # Check picking reuse
        self.assertEqual(apple_pick.state, "assigned")
        self.assertEqual(apple_pick.location_id, self.test_stock_location_01)
        self.assertEqual(apple_pick.location_dest_id, self.test_goodsout_location_01)


class TestValidateSplitting(common.BaseUDES):
    def setUp(self):
        """
        Create stock: pallet with apples, pallet with bananas
        create picking: for all of both
        """
        super(TestValidateSplitting, self).setUp()

        # group by destination location post validation
        self.picking_type_pick.write(
            {
                "u_post_validate_action": "group_by_move_line_key",
                "u_move_line_key_format": "{location_dest_id.name}",
            }
        )

        self.picking = self.create_picking(self.picking_type_pick)

    def test_check_picking_locations_split(self):
        """
        Validate self.picking into two locations and check it splits
        correctly.
        """
        apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=apple_pallet.id
        )
        banana_pallet = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 10, package_id=banana_pallet.id
        )

        products_info = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
        moves = self.create_move(self.picking, products_info)

        apple_move = moves[0]
        banana_move = moves[1]

        self.picking.action_assign()

        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids

        apple_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "qty_done": apple_move_line.product_uom_qty,
            }
        )
        banana_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_02.id,
                "qty_done": banana_move_line.product_uom_qty,
            }
        )

        self.assertEqual(apple_move_line.picking_id, self.picking)
        self.assertEqual(banana_move_line.picking_id, self.picking)

        self.picking.action_done()

        # apple and banana moves are now in different pickings
        # and the original picking has been reused.
        self.assertNotEqual(apple_move.picking_id, banana_move.picking_id)
        self.assertTrue(
            self.picking == apple_move.picking_id or self.picking == banana_move.picking_id
        )

    def test_maintain_single_pick_extra_info(self):
        """
        Check that when a move is split the picking's extra info is copied
        to the new pick.

        Extra info:
            - origin
            - partner_id
            - date_done (comes from move.date when not reusing picking)
        """
        apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=apple_pallet.id
        )
        banana_pallet = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 10, package_id=banana_pallet.id
        )

        products_info = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
        moves = self.create_move(self.picking, products_info)

        apple_move = moves[0]
        banana_move = moves[1]

        self.picking.action_assign()

        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids

        apple_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "qty_done": apple_move_line.product_uom_qty,
            }
        )
        banana_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_02.id,
                "qty_done": banana_move_line.product_uom_qty,
            }
        )

        # Prepare pick extra info to keep
        partner = self.create_partner("Test Partner 123")
        origin = "Test origin 123"
        self.picking.write({"origin": origin, "partner_id": partner.id})

        self.picking.action_done()

        # apple and banana moves are now in different pickings
        # and the original picking has been reused.
        self.assertNotEqual(apple_move.picking_id, banana_move.picking_id)
        self.assertTrue(
            self.picking == apple_move.picking_id or self.picking == banana_move.picking_id
        )

        # Check pick extra info
        self.assertEqual(origin, apple_move.picking_id.origin)
        self.assertEqual(origin, banana_move.picking_id.origin)
        self.assertEqual(partner, apple_move.picking_id.partner_id)
        self.assertEqual(partner, banana_move.picking_id.partner_id)

        # Date done of the picking is the date of the moves
        # unless it's been reused
        if self.picking == apple_move.picking_id:
            self.assertGreaterEqual(apple_move.picking_id.date_done, apple_move.date)
            self.assertEqual(banana_move.picking_id.date_done, banana_move.date)
        else:
            self.assertEqual(apple_move.picking_id.date_done, apple_move.date)
            self.assertGreaterEqual(banana_move.picking_id.date_done, banana_move.date)

    def test_maintain_two_picks_extra_info(self):
        """
        Check that when a moves from different picks are split the pickings
        extra info is copied to the new pick and maintained when two picks
        share the same info.

        Extra info:
            - origin
            - partner_id
            - date_done (comes from move.date)
        """

        # Setup pick 1
        apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=apple_pallet.id
        )
        banana_pallet = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 10, package_id=banana_pallet.id
        )

        pick1_products_info = [
            {"product": self.apple, "qty": 10},
            {"product": self.banana, "qty": 10},
        ]
        pick1_moves = self.create_move(self.picking, pick1_products_info)

        apple_move = pick1_moves[0]
        banana_move = pick1_moves[1]

        self.picking.action_assign()

        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids

        apple_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "qty_done": apple_move_line.product_uom_qty,
            }
        )
        banana_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_02.id,
                "qty_done": banana_move_line.product_uom_qty,
            }
        )

        # Setup pick 2
        self.picking_2 = self.create_picking(self.picking_type_pick)

        cherry_pallet = self.create_package()
        self.create_quant(
            self.cherry.id, self.test_stock_location_01.id, 10, package_id=cherry_pallet.id
        )
        damson_pallet = self.create_package()
        self.create_quant(
            self.damson.id, self.test_stock_location_01.id, 10, package_id=damson_pallet.id
        )

        pick2_products_info = [
            {"product": self.cherry, "qty": 10},
            {"product": self.damson, "qty": 10},
        ]
        pick2_moves = self.create_move(self.picking_2, pick2_products_info)

        cherry_move = pick2_moves[0]
        damson_move = pick2_moves[1]

        self.picking_2.action_assign()

        cherry_move_line = cherry_move.move_line_ids
        damson_move_line = damson_move.move_line_ids

        cherry_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_01.id,
                "qty_done": cherry_move_line.product_uom_qty,
            }
        )
        damson_move_line.write(
            {
                "location_dest_id": self.test_goodsout_location_02.id,
                "qty_done": damson_move_line.product_uom_qty,
            }
        )

        # Prepare both picks extra info and validate them at the same time
        both_picks = self.picking | self.picking_2

        partner = self.create_partner("Test Partner 123")
        origin = "Test origin 123"
        both_picks.write({"origin": origin, "partner_id": partner.id})
        both_picks.action_done()

        # apple and banana moves are now in different pickings.
        self.assertEqual(
            len(self.picking | apple_move.picking_id | banana_move.picking_id), 3,
        )

        self.assertEqual(apple_move.picking_id, cherry_move.picking_id)
        self.assertEqual(banana_move.picking_id, damson_move.picking_id)

        # Check pick extra info
        self.assertEqual(origin, apple_move.picking_id.origin)
        self.assertEqual(origin, banana_move.picking_id.origin)
        self.assertEqual(partner, apple_move.picking_id.partner_id)
        self.assertEqual(partner, banana_move.picking_id.partner_id)
        # Date done of the picking is the date of the move
        self.assertEqual(apple_move.picking_id.date_done, apple_move.date)
        self.assertEqual(banana_move.picking_id.date_done, banana_move.date)


class TestConfirmSplitting(common.BaseUDES):
    def setUp(self):
        """
        Create stock: pallet with apples, pallet with bananas
        create picking: for all of both
        """
        super(TestConfirmSplitting, self).setUp()

        # group by package post confirm
        self.picking_type_pick.write(
            {
                "u_post_confirm_action": "group_by_move_key",
                "u_move_key_format": "{product_id.default_code}",
            }
        )

        self.picking = self.create_picking(self.picking_type_pick)

    def test_check_pallet_split(self):
        """
        Reserve self.picking with one pallet of each product and check it
        splits correctly when confirmed.
        """
        apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 5, package_id=apple_pallet.id
        )

        banana_pallet = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 10, package_id=banana_pallet.id
        )

        products_info = [{"product": self.apple, "qty": 5}, {"product": self.banana, "qty": 10}]
        moves = self.create_move(self.picking, products_info)

        apple_move = moves[0]
        banana_move = moves[1]

        self.picking.action_confirm()

        apple_pick = apple_move.picking_id
        banana_pick = banana_move.picking_id

        # apple and banana moves are now in different pickings
        # and the original picking has been reused.
        self.assertNotEqual(apple_pick, banana_pick)
        self.assertTrue(self.picking == apple_pick or self.picking == banana_pick)

        self.assertEqual(apple_pick.move_lines, apple_move)
        self.assertEqual(banana_pick.move_lines, banana_move)
        self.assertEqual(apple_pick.state, "confirmed")
        self.assertEqual(banana_pick.state, "confirmed")
