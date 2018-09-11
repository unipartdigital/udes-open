# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import ValidationError


class TestPackageSwap(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestPackageSwap, cls).setUpClass()

    def setUp(self):
        """
        Create stock: pallet with apples, pallet with bananas
        create picking: for all of both
        """
        super(TestPackageSwap, self).setUp()
        Package = self.env['stock.quant.package']

        self.picking_type_pick.u_move_line_key_format = "{package_id.name}"

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

        self.assertEqual(self.picking.state, 'cancel')

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

        self.assertEqual(self.picking.state, 'cancel')

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

        self.assertEqual(self.picking.state, 'cancel')

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

        self.assertEqual(self.picking.state, 'cancel')

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

        self.assertEqual(self.picking.state, 'cancel')
