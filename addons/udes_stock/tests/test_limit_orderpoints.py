"""Tests for the limit orderpoints flag."""

from odoo.exceptions import ValidationError
from . import common


class LimitOrderpointsTestCase(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(LimitOrderpointsTestCase, cls).setUpClass()
        # Create an orderpoint with values
        cls.create_orderpoint(cls.apple, cls.test_output_location_01, 5, 10)

    def test01_cannot_add_orderpoint_if_one_exists(self):
        """ Tests cannot add an orderpoint if one already exists and the limit
        orderpoints flag is set on the location.
        """
        self.test_output_location_01.u_limit_orderpoints = True
        with self.assertRaises(ValidationError) as cm:
            self.create_orderpoint(self.banana,
                                   self.test_output_location_01,
                                   5, 10)
        ex = cm.exception
        self.assertEqual('An order point for location {} already exists on '
                         '{}.'.format(self.test_output_location_01.name,
                                      self.apple.name),
                         ex.name)

    def test02_cannot_add_orderpoint_if_limit_on_parent(self):
        """ Tests cannot add an orderpoint if one already exists and the limit
        orderpoints flag is set on the location's parent location.
        """
        self.out_location.u_limit_orderpoints = True
        with self.assertRaises(ValidationError) as cm:
            self.create_orderpoint(self.banana,
                                   self.test_output_location_01,
                                   5, 10)
        ex = cm.exception
        self.assertEqual('An order point for location {} already exists on '
                         '{}.'.format(self.test_output_location_01.name,
                                      self.apple.name),
                         ex.name)

    def test03_cannot_add_orderpoint_if_limit_on_grandparent(self):
        """ Tests cannot add an orderpoint if one already exists and the limit
        orderpoints flag is set on the location's grandparent location.
        """
        self.warehouse_location.u_limit_orderpoints = True
        with self.assertRaises(ValidationError) as cm:
            self.create_orderpoint(self.banana,
                                   self.test_output_location_01,
                                   5, 10)
        ex = cm.exception
        self.assertEqual('An order point for location {} already exists on '
                         '{}.'.format(self.test_output_location_01.name,
                                      self.apple.name),
                         ex.name)
