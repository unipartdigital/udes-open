# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from .common import BaseBlocked

class TestStockMove(BaseBlocked):
    def test_create_move_source_location_blocked(self):
        """ Creating a move using as source location a blocked
            location raises an error.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        picking = self.create_picking(self.picking_type_internal)
        with self.assertRaises(ValidationError) as e:
            move = self.create_move(self.apple, 10, picking,
                                    location_id=self.test_location_01.id)
        self.assertEqual(e.exception.args[0],
                         'Wrong source location creating stock move. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test_create_move_destination_location_blocked(self):
        """ Creating a move using as destination location a blocked
            location raises an error.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        picking = self.create_picking(self.picking_type_internal)
        with self.assertRaises(ValidationError) as e:
            move = self.create_move(self.apple, 10, picking,
                                    location_dest_id=self.test_location_01.id)
        self.assertEqual(e.exception.args[0],
                         'Wrong destination location creating stock move. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test_update_move_source_location_blocked(self):
        """ Updating the source location of a move using a blocked
            location raises an error.
        """
        picking = self.create_picking(self.picking_type_internal)
        move = self.create_move(self.apple, 10, picking)
        self.assertEqual(len(move), 1)
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            move.location_id=self.test_location_01
        self.assertEqual(e.exception.args[0],
                         'Wrong source location creating stock move. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test_update_move_destination_location_blocked(self):
        """ Updating the destination location of a move using a blocked
            location raises an error.
        """
        picking = self.create_picking(self.picking_type_internal)
        move = self.create_move(self.apple, 10, picking)
        self.assertEqual(len(move), 1)
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            move.location_dest_id=self.test_location_01
        self.assertEqual(e.exception.args[0],
                         'Wrong destination location creating stock move. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))
