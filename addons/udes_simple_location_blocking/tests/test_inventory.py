# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from .common import BaseBlocked

class TestStockInventory(BaseBlocked):
    def test01_create_inventory_location_blocked(self):
        """ Creating an inventory using a blocked location
            raises an error.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True

        with self.assertRaises(ValidationError) as e:
            inventory = self.create_inventory(self.test_location_01)
        self.assertEqual(e.exception.name,
                'Cannot create inventory adjustment. Location %s is'
                ' blocked (reason: %s). Please speak'
                ' to a team leader to resolve the issue.' %
                (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test02_create_inventory_lines_location_blocked(self):
        """ Creating an inventory line from a blocked location
            raises an error.
        """
        inventory = self.create_inventory(self.test_location_01)
        self.create_quant(self.apple.id, self.test_location_01.id, 10)
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            inventory.action_start()
        self.assertEqual(e.exception.name,
                'Cannot create inventory adjustment line. Location %s is'
                ' blocked (reason: %s). Please speak'
                ' to a team leader to resolve the issue.' %
                (self.test_location_01.name, self.test_location_01.u_blocked_reason))
                
    def test03_validate_inventory_location_blocked(self):
        """ Validating an inventory of a blocked location
            raises an error.
        """
        inventory = self.create_inventory(self.test_location_01)
        self.create_quant(self.apple.id, self.test_location_01.id, 10)
        inventory.action_start()
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            inventory._action_done()
        self.assertEqual(e.exception.name,
                'Cannot validate inventory adjustment. Location %s is'
                ' blocked (reason: %s). Please speak'
                ' to a team leader to resolve the issue.' %
                (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test04_validate_inventory_line_location_blocked(self):
        """ Validating an inventory line of a blocked location
            raises an error.
        """
        inventory = self.create_inventory(self.stock_location)
        self.create_quant(self.apple.id, self.test_location_01.id, 10)
        inventory.action_start()
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        with self.assertRaises(ValidationError) as e:
            inventory._action_done()
        self.assertEqual(e.exception.name,
                'Cannot validate inventory adjustment line. Location %s is'
                ' blocked (reason: %s). Please speak'
                ' to a team leader to resolve the issue.' %
                (self.test_location_01.name, self.test_location_01.u_blocked_reason))

    def test05_validate_inventory_location_non_blocked(self):
        """ Validating an inventory of a non blocked location
            does not raise an error.
            Change 10 apples to 9.
        """
        Location = self.env['stock.location']
        # create sublocation for test_location_01
        test_location_01_01 = Location.create({
                'name': "Test location 01 01",
                'barcode': "LTEST0101",
                'location_id': self.test_location_01.id,
            })
        # create inventory for test_location_01
        inventory = self.create_inventory(self.test_location_01)
        # create quant at the sublocation
        quant = self.create_quant(self.apple.id, test_location_01_01.id, 10)
        inventory.action_start()
        apple_line = inventory.line_ids.filtered(lambda l: l.product_id == self.apple)
        apple_line.product_qty = 9
        inventory._action_done()
        self.assertEqual(quant.quantity, 9)

