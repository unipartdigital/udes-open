# -*- coding: utf-8 -*-

from . import common


class TestAssignSplitting(common.BaseUDES):

    def setUp(self):
        """
        Create stock: pallet with apples, pallet with bananas
        create picking: for all of both
        """
        super(TestAssignSplitting, self).setUp()

        # group by package post assign
        self.picking_type_pick.write({
            'u_post_assign_action': 'group_by_move_line_key',
            'u_move_line_key_format': "{package_id.name}",
        })

        self.picking = self.create_picking(self.picking_type_pick)

    def test01_simple(self):
        """Reserve self.picking with one pallet of each product and check it
        splits correctly when reserved."""
        Picking = self.env['stock.picking']
        apple_pallet = self.create_package()
        self.create_quant(self.apple.id, self.test_location_01.id,
                          10, package_id=apple_pallet.id)
        banana_pallet = self.create_package()
        self.create_quant(self.banana.id, self.test_location_01.id,
                          10, package_id=banana_pallet.id)

        self.create_move(self.apple, 10, self.picking)
        self.create_move(self.banana, 10, self.picking)
        self.picking.action_assign()

        apple_pick = Picking.get_pickings(package_name=apple_pallet.name)
        banana_pick = Picking.get_pickings(package_name=banana_pallet.name)

        self.assertEqual(apple_pick.state, 'assigned')
        self.assertEqual(banana_pick.state, 'assigned')
        self.assertEqual(apple_pick.group_id.name, apple_pallet.name)
        self.assertEqual(banana_pick.group_id.name, banana_pallet.name)

        # Check we haven't mangled the moves or move_lines
        apple_move = apple_pick.move_lines
        self.assertEqual(len(apple_move), 1)
        self.assertEqual(apple_move.product_uom_qty, 10)
        apple_ml = apple_pick.move_line_ids
        self.assertEqual(len(apple_ml), 1)
        self.assertEqual(apple_ml.product_qty, 10)
        self.assertEqual(apple_ml.package_id, apple_pallet)
        self.assertEqual(apple_ml.result_package_id, apple_pallet)
        self.assertEqual(apple_ml.product_id, self.apple)

        banana_move = banana_pick.move_lines
        self.assertEqual(len(banana_move), 1)
        self.assertEqual(banana_move.product_uom_qty, 10)
        banana_ml = banana_pick.move_line_ids
        self.assertEqual(len(banana_ml), 1)
        self.assertEqual(banana_ml.product_qty, 10)
        self.assertEqual(banana_ml.package_id, banana_pallet)
        self.assertEqual(banana_ml.result_package_id, banana_pallet)
        self.assertEqual(banana_ml.product_id, self.banana)

        # Check that the original picking has been reused
        self.assertTrue(self.picking.exists())

    def test02_split_move(self):
        """Reserve self.picking with two pallet of the same product and check it
        splits correctly when reserved."""
        Picking = self.env['stock.picking']
        cherry_pallet1 = self.create_package()
        self.create_quant(self.cherry.id, self.test_location_01.id,
                          10, package_id=cherry_pallet1.id)
        cherry_pallet2 = self.create_package()
        self.create_quant(self.cherry.id, self.test_location_01.id,
                          10, package_id=cherry_pallet2.id)
        self.create_move(self.cherry, 20, self.picking)
        self.picking.action_assign()

        pick1 = Picking.get_pickings(package_name=cherry_pallet1.name)
        pick2 = Picking.get_pickings(package_name=cherry_pallet2.name)

        self.assertEqual(pick1.state, 'assigned')
        self.assertEqual(pick2.state, 'assigned')
        self.assertEqual(pick1.group_id.name, cherry_pallet1.name)
        self.assertEqual(pick2.group_id.name, cherry_pallet2.name)

        # Check we haven't mangled the moves or move_lines
        p1_move = pick1.move_lines
        self.assertEqual(len(p1_move), 1)
        self.assertEqual(p1_move.product_uom_qty, 10)
        p1_ml = pick1.move_line_ids
        self.assertEqual(len(p1_ml), 1)
        self.assertEqual(p1_ml.product_qty, 10)
        self.assertEqual(p1_ml.package_id, cherry_pallet1)
        self.assertEqual(p1_ml.result_package_id, cherry_pallet1)
        self.assertEqual(p1_ml.product_id, self.cherry)

        p2_move = pick2.move_lines
        self.assertEqual(len(p2_move), 1)
        self.assertEqual(p2_move.product_uom_qty, 10)
        p2_ml = pick2.move_line_ids
        self.assertEqual(len(p2_ml), 1)
        self.assertEqual(p2_ml.product_qty, 10)
        self.assertEqual(p2_ml.package_id, cherry_pallet2)
        self.assertEqual(p2_ml.result_package_id, cherry_pallet2)
        self.assertEqual(p2_ml.product_id, self.cherry)

        # Check that the original picking has been reused
        self.assertTrue(self.picking.exists())

    def test03_two_products_in_pallet(self):
        """Reserve self.picking with a pallet containing two different products
        and check it splits correctly when reserved."""
        Picking = self.env['stock.picking']
        mixed_pallet = self.create_package()
        self.create_quant(self.fig.id, self.test_location_01.id,
                          5, package_id=mixed_pallet.id)
        self.create_quant(self.grape.id, self.test_location_01.id,
                          10, package_id=mixed_pallet.id)
        self.create_move(self.fig, 5, self.picking)
        self.create_move(self.grape, 10, self.picking)
        self.picking.action_assign()

        pick = Picking.get_pickings(package_name=mixed_pallet.name)

        self.assertEqual(pick.state, 'assigned')
        self.assertEqual(pick.group_id.name, mixed_pallet.name)

        # Check we haven't mangled the moves or move_lines
        moves = pick.move_lines
        self.assertEqual(len(moves), 2)
        fig_move = moves.filtered(lambda m: m.product_id == self.fig)
        self.assertEqual(fig_move.product_uom_qty, 5)
        grape_move = moves.filtered(lambda m: m.product_id == self.grape)
        self.assertEqual(grape_move.product_uom_qty, 10)
        mls = pick.move_line_ids
        self.assertEqual(len(mls), 2)
        fig_ml = mls.filtered(lambda ml: ml.product_id == self.fig)
        self.assertEqual(fig_ml.product_qty, 5)
        self.assertEqual(fig_ml.package_id, mixed_pallet)
        self.assertEqual(fig_ml.result_package_id, mixed_pallet)
        grape_ml = mls.filtered(lambda ml: ml.product_id == self.grape)
        self.assertEqual(grape_ml.product_qty, 10)
        self.assertEqual(grape_ml.package_id, mixed_pallet)
        self.assertEqual(grape_ml.result_package_id, mixed_pallet)

        # Check that the original picking has been reused
        self.assertTrue(self.picking.exists())

    def test04_combine_two_pickings_at_reserve(self):
        """Create two pickings for two items on the same pallet. Reserve them
        simultaneously and check they result in one picking with two moves.
        """
        Picking = self.env['stock.picking']
        pallet = self.create_package()
        self.create_quant(self.elderberry.id, self.test_location_01.id,
                          5, package_id=pallet.id)
        self.create_quant(self.elderberry.id, self.test_location_01.id,
                          10, package_id=pallet.id)
        p1 = self.picking
        p2 = self.create_picking(self.picking_type_pick)
        m1 = self.create_move(self.elderberry, 5, p1)
        m2 = self.create_move(self.elderberry, 10, p2)
        (p1 | p2).action_assign()

        pick = Picking.get_pickings(package_name=pallet.name)

        self.assertEqual(pick.state, 'assigned')
        self.assertEqual(pick.group_id.name, pallet.name)

        # Check we haven't mangled the moves or move_lines
        self.assertEqual((m1 | m2).ids, pick.move_lines.ids)

        mls = pick.move_line_ids
        self.assertEqual(len(mls), 2)
        ml1 = mls.filtered(lambda ml: ml.move_id == m1)
        self.assertEqual(ml1.product_qty, 5)
        self.assertEqual(ml1.package_id, pallet)
        self.assertEqual(ml1.product_id, self.elderberry)
        ml2 = mls.filtered(lambda ml: ml.move_id == m2)
        self.assertEqual(ml2.product_qty, 10)
        self.assertEqual(ml2.package_id, pallet)
        self.assertEqual(ml2.product_id, self.elderberry)

        # Check that neither picking has been reused, empty pickings have been
        # marked (u_mark = False) and deleted at the very end of the action
        self.assertFalse(p1.exists())
        self.assertFalse(p2.exists())

    def test05_add_to_existing_picking(self):
        """Create two pickings for two items on the same pallet. Reserve them
        sequentially and check they result in one picking with two moves.
        """
        Picking = self.env['stock.picking']
        pallet = self.create_package()
        self.create_quant(self.elderberry.id, self.test_location_01.id,
                          5, package_id=pallet.id)
        self.create_quant(self.elderberry.id, self.test_location_01.id,
                          10, package_id=pallet.id)
        p1 = self.picking
        p2 = self.create_picking(self.picking_type_pick)
        m1 = self.create_move(self.elderberry, 5, p1)
        m2 = self.create_move(self.elderberry, 10, p2)
        p1.action_assign()
        p2.action_assign()

        pick = Picking.get_pickings(package_name=pallet.name)

        self.assertEqual(pick.state, 'assigned')
        self.assertEqual(pick.group_id.name, pallet.name)

        # Check we haven't mangled the moves or move_lines
        self.assertEqual((m1 | m2).ids, pick.move_lines.ids)

        mls = pick.move_line_ids
        self.assertEqual(len(mls), 2)
        ml1 = mls.filtered(lambda ml: ml.move_id == m1)
        self.assertEqual(ml1.product_qty, 5)
        self.assertEqual(ml1.package_id, pallet)
        self.assertEqual(ml1.product_id, self.elderberry)
        ml2 = mls.filtered(lambda ml: ml.move_id == m2)
        self.assertEqual(ml2.product_qty, 10)
        self.assertEqual(ml2.package_id, pallet)
        self.assertEqual(ml2.product_id, self.elderberry)

        # Check that the first picking has been reused and the second picking
        # has been marked as empty (u_mark = False) and deleted at the very end
        # of the action
        self.assertTrue(p1.exists())
        self.assertFalse(p2.exists())

    def test06_persist_locations(self):
        """Reserve when the locations of the picking are not the defaults of
        the picking type and check the non-defaults are maintained."""
        Picking = self.env['stock.picking']

        self.picking.write({
            'location_id': self.test_location_01.id,
            'location_dest_id': self.test_output_location_01.id
        })

        apple_pallet = self.create_package()
        self.create_quant(self.apple.id, self.test_location_01.id,
                          10, package_id=apple_pallet.id)
        self.create_move(self.apple, 10, self.picking)

        self.picking.action_assign()

        apple_pick = Picking.get_pickings(package_name=apple_pallet.name)
        self.assertEqual(self.picking, apple_pick) # Check picking reuse
        self.assertEqual(apple_pick.state, 'assigned')
        self.assertEqual(apple_pick.location_id.id, self.test_location_01.id)
        self.assertEqual(apple_pick.location_dest_id.id, self.test_output_location_01.id)


class TestValidateSplitting(common.BaseUDES):

    def setUp(self):
        """
        Create stock: pallet with apples, pallet with bananas
        create picking: for all of both
        """
        super(TestValidateSplitting, self).setUp()

        # group by destination location post validation
        self.picking_type_pick.write({
            'u_post_validate_action': 'group_by_move_line_key',
            'u_move_line_key_format': "{location_dest_id.name}",
        })

        self.picking = self.create_picking(self.picking_type_pick)

    def test01_simple(self):
        """Validate self.picking into two locations and check it splits
        correctly."""
        apple_pallet = self.create_package()
        self.create_quant(self.apple.id, self.test_location_01.id,
                          10, package_id=apple_pallet.id)
        banana_pallet = self.create_package()
        self.create_quant(self.banana.id, self.test_location_01.id,
                          10, package_id=banana_pallet.id)

        apple_move = self.create_move(self.apple, 10, self.picking)
        banana_move = self.create_move(self.banana, 10, self.picking)
        self.picking.action_assign()

        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids

        apple_move_line.write({
            'location_dest_id': self.test_output_location_01.id,
            'qty_done': apple_move_line.product_uom_qty
        })
        banana_move_line.write({
            'location_dest_id': self.test_output_location_02.id,
            'qty_done': banana_move_line.product_uom_qty
        })

        self.assertEqual(apple_move_line.picking_id.id, self.picking.id)
        self.assertEqual(banana_move_line.picking_id.id, self.picking.id)

        self.picking.action_done()

        # apple and banana moves are now in different pickings
        # and the original picking has been reused.
        self.assertNotEqual(apple_move.picking_id, banana_move.picking_id)
        self.assertTrue(self.picking == apple_move.picking_id or
                        self.picking == banana_move.picking_id)

    def test02_maintain_single_pick_extra_info(self):
        """ Check that when a move is split the picking's extra info is copied
            to the new pick.
            Extra info:
            - origin
            - partner_id
            - date_done (comes from move.date when not reusing picking)
        """
        apple_pallet = self.create_package()
        self.create_quant(self.apple.id, self.test_location_01.id,
                          10, package_id=apple_pallet.id)
        banana_pallet = self.create_package()
        self.create_quant(self.banana.id, self.test_location_01.id,
                          10, package_id=banana_pallet.id)

        apple_move = self.create_move(self.apple, 10, self.picking)
        banana_move = self.create_move(self.banana, 10, self.picking)
        self.picking.action_assign()

        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids

        apple_move_line.write({
            'location_dest_id': self.test_output_location_01.id,
            'qty_done': apple_move_line.product_uom_qty
        })
        banana_move_line.write({
            'location_dest_id': self.test_output_location_02.id,
            'qty_done': banana_move_line.product_uom_qty
        })

        # Prepare pick extra info to keep
        partner = self.create_partner('Test Partner 123')
        origin = "Test origin 123"
        self.picking.write({'origin': origin,
                            'partner_id': partner.id})

        self.picking.action_done()

        # apple and banana moves are now in different pickings
        # and the original picking has been reused.
        self.assertNotEqual(apple_move.picking_id, banana_move.picking_id)
        self.assertTrue(self.picking == apple_move.picking_id or
                        self.picking == banana_move.picking_id)

        # Check pick extra info
        self.assertEqual(origin, apple_move.picking_id.origin)
        self.assertEqual(origin, banana_move.picking_id.origin)
        self.assertEqual(partner,
                         apple_move.picking_id.partner_id)
        self.assertEqual(partner,
                         banana_move.picking_id.partner_id)

        # Date done of the picking is the date of the moves
        # unless it's been reused
        if self.picking == apple_move.picking_id:
            self.assertGreaterEqual(apple_move.picking_id.date_done, apple_move.date)
            self.assertEqual(banana_move.picking_id.date_done, banana_move.date)
        else:
            self.assertEqual(apple_move.picking_id.date_done, apple_move.date)
            self.assertGreaterEqual(banana_move.picking_id.date_done, banana_move.date)

    def test02_maintain_two_picks_extra_info(self):
        """ Check that when a moves from different picks are split the pickings
            extra info is copied to the new pick and maintained when two picks
            share the same info.
            Extra info:
            - origin
            - partner_id
            - date_done (comes from move.date)
        """

        # Setup pick 1
        apple_pallet = self.create_package()
        self.create_quant(self.apple.id, self.test_location_01.id,
                          10, package_id=apple_pallet.id)
        banana_pallet = self.create_package()
        self.create_quant(self.banana.id, self.test_location_01.id,
                          10, package_id=banana_pallet.id)

        apple_move = self.create_move(self.apple, 10, self.picking)
        banana_move = self.create_move(self.banana, 10, self.picking)
        self.picking.action_assign()

        apple_move_line = apple_move.move_line_ids
        banana_move_line = banana_move.move_line_ids

        apple_move_line.write({
            'location_dest_id': self.test_output_location_01.id,
            'qty_done': apple_move_line.product_uom_qty
        })
        banana_move_line.write({
            'location_dest_id': self.test_output_location_02.id,
            'qty_done': banana_move_line.product_uom_qty
        })

        # Setup pick 2
        self.picking_2 = self.create_picking(self.picking_type_pick)

        cherry_pallet = self.create_package()
        self.create_quant(self.cherry.id, self.test_location_01.id,
                          10, package_id=cherry_pallet.id)
        damson_pallet = self.create_package()
        self.create_quant(self.damson.id, self.test_location_01.id,
                          10, package_id=damson_pallet.id)

        cherry_move = self.create_move(self.cherry, 10, self.picking_2)
        damson_move = self.create_move(self.damson, 10, self.picking_2)
        self.picking_2.action_assign()

        cherry_move_line = cherry_move.move_line_ids
        damson_move_line = damson_move.move_line_ids

        cherry_move_line.write({
            'location_dest_id': self.test_output_location_01.id,
            'qty_done': cherry_move_line.product_uom_qty
        })
        damson_move_line.write({
            'location_dest_id': self.test_output_location_02.id,
            'qty_done': damson_move_line.product_uom_qty
        })

        # Prepare both picks extra info and validate them at the same time
        both_picks = (self.picking | self.picking_2)

        partner = self.create_partner('Test Partner 123')
        origin = "Test origin 123"
        both_picks.write({'origin': origin,
                          'partner_id': partner.id})
        both_picks.action_done()

        # apple and banana moves are now in different pickings.
        self.assertEqual(
            len(self.picking | apple_move.picking_id | banana_move.picking_id),
            3,
        )

        self.assertEqual(apple_move.picking_id.id, cherry_move.picking_id.id)
        self.assertEqual(banana_move.picking_id.id, damson_move.picking_id.id)

        # Check pick extra info
        self.assertEqual(origin, apple_move.picking_id.origin)
        self.assertEqual(origin, banana_move.picking_id.origin)
        self.assertEqual(partner,
                         apple_move.picking_id.partner_id)
        self.assertEqual(partner,
                         banana_move.picking_id.partner_id)
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
        self.picking_type_pick.write({
            'u_post_confirm_action': 'group_by_move_key',
            'u_move_key_format': "{product_id.default_code}",
        })

        self.picking = self.create_picking(self.picking_type_pick)

    def test01_simple(self):
        """Reserve self.picking with one pallet of each product and check it
           splits correctly when confirmed.
        """
        apple_pallet = self.create_package()
        self.create_quant(
            self.apple.id,
            self.test_location_01.id,
            5,
            package_id=apple_pallet.id)

        banana_pallet = self.create_package()
        self.create_quant(
            self.banana.id,
            self.test_location_02.id,
            10,
            package_id=banana_pallet.id)

        apple_move = self.create_move(self.apple, 5, self.picking)
        banana_move = self.create_move(self.banana, 10, self.picking)
        self.picking.action_confirm()

        apple_pick = apple_move.picking_id
        banana_pick = banana_move.picking_id

        # apple and banana moves are now in different pickings
        # and the original picking has been reused.
        self.assertNotEqual(apple_pick, banana_pick)
        self.assertTrue(self.picking == apple_pick or
                        self.picking == banana_pick)

        self.assertEqual(apple_pick.move_lines, apple_move)
        self.assertEqual(banana_pick.move_lines, banana_move)
        self.assertEqual(apple_pick.state, 'confirmed')
        self.assertEqual(banana_pick.state, 'confirmed')


class TestAutoUnlinkEmpty(common.BaseUDES):
    def setUp(self):
        """ Setup picking type config
        """
        super(TestAutoUnlinkEmpty, self).setUp()

        # group by product post confirm at goods-out
        self.picking_type_out.write({
            'u_post_confirm_action': 'group_by_move_key',
            'u_move_key_format': "{product_id.default_code}",
        })

    def _count_out_pickings(self):
        Picking = self.env['stock.picking']

        return Picking.search_count([
            ('picking_type_id', '=', self.picking_type_out.id)
        ])

    def test01_auto_unlink_empty_pickings(self):
        """ Check that unlink_empty finds any picking in the system marked as
            empty and that when auto unlink empty is disabled for goods-out any
            empty picking is not deleted when searching for any picking.

            Create two different picks for the same product, confirm them one
            by one so the goods-out picking is reused leaving one empty picking
            for the second picking.
        """
        Picking = self.env['stock.picking']

        # Create first pick for apples
        pick_1 = self.create_picking(self.picking_type_pick)
        move_1 = self.create_move(self.apple, 5, pick_1)
        # Action_confirm triggers push route which creates goods-out picking
        pick_1.action_confirm()
        out_1 = pick_1.u_next_picking_ids
        self.assertTrue(out_1.exists())

        # There is at least one out picking
        n_out_pickings = self._count_out_pickings()
        self.assertTrue(n_out_pickings > 0)

        # Create second pick for apples
        pick_2 = self.create_picking(self.picking_type_pick)
        move_2 = self.create_move(self.apple, 5, pick_2)
        # action_confirm triggers push route which creates goods-out picking
        pick_2.action_confirm()
        out_2 = pick_2.u_next_picking_ids

        # The refactoring reuses out_1 because it is the same product
        self.assertEqual(out_1, out_2)

        # There is one more picking
        self.assertEqual(n_out_pickings + 1, self._count_out_pickings())
        # Disable auto unlink empty at out picking type
        self.picking_type_out.u_auto_unlink_empty = False
        Picking.unlink_empty()
        # There is still only one more picking
        self.assertEqual(n_out_pickings + 1, self._count_out_pickings())
        # Enable auto unlink empty at out picking type
        self.picking_type_out.u_auto_unlink_empty = True
        Picking.unlink_empty()
        # Empty picking has disappeared
        self.assertEqual(n_out_pickings, self._count_out_pickings())
