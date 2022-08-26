# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from .common import BaseBlocked

class TestStockPicking(BaseBlocked):
    def test_create_picking_source_location_blocked(self):
        """ Creating a picking using as source location a blocked
            location raises an error.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            picking = self.create_picking(self.picking_type_internal,
                                          location_id=self.test_location_01.id)
        self.assertEqual(e.exception.args[0],
                         'Wrong source location creating transfer. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test_create_picking_destination_location_blocked(self):
        """ Creating a picking using as destination location a blocked
            location raises an error.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            picking = self.create_picking(self.picking_type_internal,
                                          location_dest_id=self.test_location_01.id)
        self.assertEqual(e.exception.args[0],
                         'Wrong destination location creating transfer. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test_update_picking_source_location_blocked(self):
        """ Updating the source location of a picking using a blocked
            location raises an error.
        """
        picking = self.create_picking(self.picking_type_internal)
        self.assertEqual(len(picking), 1)
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            picking.location_id=self.test_location_01
        self.assertEqual(e.exception.args[0],
                         'Wrong source location creating transfer. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test_update_picking_destination_location_blocked(self):
        """ Updating the destination location of a picking using a blocked
            location raises an error.
        """
        picking = self.create_picking(self.picking_type_internal)
        self.assertEqual(len(picking), 1)
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            picking.location_dest_id=self.test_location_01
        self.assertEqual(e.exception.args[0],
                         'Wrong destination location creating transfer. Location %s '
                         'is blocked (reason: %s). Please speak'
                         ' to a team leader to resolve the issue.' % 
                         (self.test_location_01.name, self.test_location_01.u_blocked_reason))