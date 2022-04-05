# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from .common import BaseBlocked

class TestStockQuant(BaseBlocked):
    def setUp(self):
        super(TestStockQuant, self).setUp()
        # create 10 apples at test_location_01 for all the tests
        self.create_quant(self.apple.id, self.test_location_01.id, 10)

    def test01_gather_blocked_location(self):
        """ Gather quants from a blocked location should return
            an empty recordset.
        """
        Quant = self.env['stock.quant']
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        quants = Quant._gather(self.apple, self.test_location_01)
        self.assertEqual(len(quants), 0)

    def test02_gather_non_blocked_location(self):
        """ Gather quants from a non blocked location should return
            the quants at that location.
        """
        Quant = self.env['stock.quant']
        quants = Quant._gather(self.apple, self.test_location_01)
        self.assertEqual(len(quants), 1)

    def test03_gather_parent_of_one_blocked_location(self):
        """ Gather quants from a parent location of a blocked location
            should return an empty recordset.
        """
        Quant = self.env['stock.quant']
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        quants = Quant._gather(self.apple, self.stock_location)
        self.assertEqual(len(quants), 0)

    def test04_gather_parent_of_two_locations_one_blocked(self):
        """ Gather quants from a parent location of two locations, where
            one of them is blocked should return the quants of the non
            blocked location.
        """
        Quant = self.env['stock.quant']
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        self.create_quant(self.apple.id, self.test_location_02.id, 10)
        quants = Quant._gather(self.apple, self.stock_location)
        self.assertEqual(len(quants), 1)
