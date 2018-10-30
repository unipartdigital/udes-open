# -*- coding: utf-8 -*-
import unittest

from . import common


class PushFromDropBase(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        """Setup branching Inbound flow
        Goods In: Customers to Input
        Putaway: Input to Stock

        Putaway Push: Input/Received to Stock
        Damaged Push: Input/Damaged to QC

        Putaway Push and Damaged Push both push from drop.
        """
        super(PushFromDropBase, cls).setUpClass()

        Location = cls.env['stock.location']
        Push = cls.env['stock.location.path']

        input_zone = cls.env.ref('stock.stock_location_company')
        input_zone.usage = 'view'
        cls.picking_type_in.default_location_dest_id = input_zone.id
        cls.picking_type_putaway.default_location_src_id = input_zone.id

        cls.received_location.location_id = input_zone
        cls.received_damaged_location = Location.create({
            'name': "TEST_RECEIVEDDAMAGED",
            'barcode': "LTESTRECEIVEDDAMAGED",
            'location_id': input_zone.id,
        })

        cls.location_qc_zone = Location.create({
            'name': "QC Stock",
            'usage': 'view',
        })
        cls.location_qc_01 = Location.create({
            'name': "QC Stock 01",
            'barcode': "LTESTQC01",
            'location_id': cls.location_qc_zone.id,
        })

        # Update path_in_putaway to use correct location:
        cls.push_putaway.write({
            "location_from_id": cls.received_location.id,
            "u_push_on_drop": True,
        })

        cls.push_damaged_putaway = Push.create({
            "name": "TestDamagedPutaway",
            "route_id": cls.route_in.id,
            "sequence": 30,
            "location_from_id": cls.received_damaged_location.id,
            "location_dest_id": cls.location_qc_zone.id,
            "picking_type_id": cls.picking_type_putaway.id,
            "u_push_on_drop": True,
        })

    def setUp(self):
        """
        Ensure all tests start with push_from_drop set to True
        """
        super(PushFromDropBase, self).setUp()
        self.push_putaway.u_push_on_drop = True
        self.push_damaged_putaway.u_push_on_drop = True


class TestGetPathFromLocation(PushFromDropBase):
    """Tests for the stock.location.path.get_path_from_location method in
    isolation"""
    def test01_no_route(self):
        """Test that get_path_from_location returns an empty recordset when no
        matching path is found"""
        Push = self.env['stock.location.path']
        self.push_damaged_putaway.unlink()
        res = Push.get_path_from_location(self.received_damaged_location)
        self.assertFalse(res)

    def test02_one_route(self):
        """Test that get_path_from_location returns a single matching path when
        one exists"""
        Push = self.env['stock.location.path']
        res = Push.get_path_from_location(self.received_damaged_location)
        self.assertEqual(res, self.push_damaged_putaway)

    def test03_many_routes(self):
        """Test that get_path_from_location returns a single matching path when
        more than one possible match exists, and the returned value is the one
        for the closest parent of the search location.
        """
        Push = self.env['stock.location.path']
        input_zone = self.env.ref('stock.stock_location_company')

        # create new push from the Input zone.
        Push.create({
            "name": "TestPushMultiRoute",
            "route_id": self.route_in.id,
            "sequence": 40,
            "location_from_id": input_zone.id,
            "location_dest_id": self.location_qc_zone.id,
            "picking_type_id": self.picking_type_putaway.id,
            "u_push_on_drop": True,
        })
        # Damaged route found correctly
        res = Push.get_path_from_location(self.received_damaged_location)
        self.assertEqual(res, self.push_damaged_putaway)

        # Non-damaged route found correctly
        res = Push.get_path_from_location(self.received_location)
        self.assertEqual(res, self.push_putaway)


class TestCreateMovesForPush(PushFromDropBase):
    """Tests for the stock.move._create_moves_for_push method in
    isolation"""
    def setUp(self):
        """Create a picking to work with for tests"""
        super(TestCreateMovesForPush, self).setUp()
        products_info = [{'product': self.apple, 'qty': 10},
                         {'product': self.banana, 'qty': 99}]
        self.goods_in = self.create_picking(self.picking_type_in,
                                            products_info=products_info)
        self.goods_in.action_confirm()
        self.goods_in.action_assign()
        self.move_lines = self.goods_in.move_line_ids
        for ml in self.move_lines:
            ml.write({'qty_done': ml.product_uom_qty})

    def test01_correct_move_qty(self):
        """Test that created moves have the correct quantity"""
        Move = self.env['stock.move']
        res = Move._create_moves_for_push(self.push_damaged_putaway,
                                          self.move_lines)
        self.assertEqual(len(res), 2)
        new_apple_move = res.filtered(lambda m: m.product_id.id == self.apple.id)
        new_banana_move = res.filtered(lambda m: m.product_id.id == self.banana.id)

        self.assertEqual(new_apple_move.product_uom_qty, 10)
        self.assertEqual(new_banana_move.product_uom_qty, 99)

    def test02_correct_move_locations(self):
        """Test that created moves have the correct src and dest locations"""
        Move = self.env['stock.move']
        res = Move._create_moves_for_push(self.push_damaged_putaway,
                                          self.move_lines)

        self.assertEqual(len(res), 2)
        for move in res:
            self.assertEqual(move.location_id, self.received_damaged_location)
            self.assertEqual(move.location_dest_id, self.location_qc_zone)

    def test03_correct_move_orig_info(self):
        """Test that created moves set move_orig_ids correctly"""
        Move = self.env['stock.move']

        moves = self.goods_in.mapped('move_lines')
        apple_move = moves.filtered(lambda m: m.product_id.id == self.apple.id)
        banana_move = moves.filtered(lambda m: m.product_id.id == self.banana.id)
        self.assertFalse(apple_move.move_dest_ids)
        self.assertFalse(banana_move.move_dest_ids)

        res = Move._create_moves_for_push(self.push_damaged_putaway,
                                          self.move_lines)

        self.assertEqual(len(res), 2)
        new_apple_move = res.filtered(lambda m: m.product_id.id == self.apple.id)
        new_banana_move = res.filtered(lambda m: m.product_id.id == self.banana.id)
        self.assertEqual(new_apple_move.move_orig_ids, apple_move)
        self.assertEqual(new_banana_move.move_orig_ids, banana_move)


class TestPushFromDrop(PushFromDropBase):
    """Tests for the full push from drop functionality"""
    def setUp(self):
        """Create a picking to work with for tests"""
        super(TestPushFromDrop, self).setUp()
        products_info = [{'product': self.apple, 'qty': 10},
                         {'product': self.banana, 'qty': 99}]
        self.goods_in = self.create_picking(self.picking_type_in,
                                            products_info=products_info)
        self.goods_in.action_confirm()
        self.goods_in.action_assign()
        self.move_lines = self.goods_in.move_line_ids
        for ml in self.move_lines:
            ml.write({'qty_done': ml.product_uom_qty})

    def test01_picking_has_correct_src_and_dest(self):
        """Test that pickings created by push from drop have the src and dest
        location of the rule that created them."""
        for ml in self.move_lines:
            ml.write({'qty_done': ml.product_uom_qty,
                      'location_dest_id': self.received_damaged_location.id})
        self.goods_in.action_done()
        putaway = self.goods_in.u_next_picking_ids
        self.assertEqual(len(putaway), 1)
        self.assertEqual(putaway.location_id, self.received_damaged_location)
        self.assertEqual(putaway.location_dest_id, self.location_qc_zone)

    def test02_no_push_rule(self):
        """Test that when no push rule exists nothing is created"""
        (self.push_damaged_putaway + self.push_putaway).unlink()
        for ml in self.move_lines:
            ml.write({'qty_done': ml.product_uom_qty,
                      'location_dest_id': self.received_damaged_location.id})
        self.goods_in.action_done()
        putaway = self.goods_in.u_next_picking_ids
        self.assertEqual(len(putaway), 0)

    def test03_stock_is_reserved(self):
        """Test that when a push occurs, stock is reserved and available to move
        further."""
        for ml in self.move_lines:
            ml.write({'qty_done': ml.product_uom_qty,
                      'location_dest_id': self.received_damaged_location.id})
        self.goods_in.action_done()
        putaway = self.goods_in.u_next_picking_ids
        self.assertEqual(len(putaway), 1)
        self.assertEqual(putaway.state, 'assigned')

    def test04_picking_can_be_completed(self):
        """Test that when a picking is created by push_from_drop it can be
        validated."""
        for ml in self.move_lines:
            ml.write({'qty_done': ml.product_uom_qty,
                      'location_dest_id': self.received_damaged_location.id})
        self.goods_in.action_done()
        putaway = self.goods_in.u_next_picking_ids
        self.assertEqual(len(putaway), 1)
        self.assertEqual(putaway.state, 'assigned')
        for ml in putaway.move_line_ids:
            ml.write({'qty_done': ml.product_uom_qty,
                      'location_dest_id': self.location_qc_01.id})
        putaway.action_done()
        self.assertEqual(putaway.state, 'done')
