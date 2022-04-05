# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from .common import BaseBlocked

class TestStockMoveLine(BaseBlocked):
    def test01_create_move_line_source_location_blocked(self):
        """ Creating a move line using as source location a blocked
            location raises an error.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        picking = self.create_picking(self.picking_type_internal)
        move = self.create_move(self.apple, 10, picking)
        with self.assertRaises(ValidationError) as e:
            move_line = self.create_move_line(move, 10,
                                    location_id=self.test_location_01.id)
        self.assertEqual(e.exception.name,
                         'Wrong source location creating stock move line. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test02_create_move_line_destination_location_blocked(self):
        """ Creating a move line using as destination location a blocked
            location raises an error.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        picking = self.create_picking(self.picking_type_internal)
        move = self.create_move(self.apple, 10, picking)
        with self.assertRaises(ValidationError) as e:
            move_line = self.create_move_line(move, 10,
                                    location_dest_id=self.test_location_01.id)
        self.assertEqual(e.exception.name,
                         'Wrong destination location creating stock move line. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test03_update_move_line_source_location_blocked(self):
        """ Updating the source location of a move line using a blocked
            location raises an error.
        """
        picking = self.create_picking(self.picking_type_internal)
        move = self.create_move(self.apple, 10, picking)
        move_line = self.create_move_line(move, 10)
        self.assertEqual(len(move), 1)
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            move_line.location_id=self.test_location_01
        self.assertEqual(e.exception.name,
                         'Wrong source location creating stock move line. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test04_update_move_line_destination_location_blocked(self):
        """ Updating the destination location of a move line using a blocked
            location raises an error.
        """
        picking = self.create_picking(self.picking_type_internal)
        move = self.create_move(self.apple, 10, picking)
        move_line = self.create_move_line(move, 10)
        self.assertEqual(len(move), 1)
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            move_line.location_dest_id=self.test_location_01
        self.assertEqual(e.exception.name,
                         'Wrong destination location creating stock move line. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))
