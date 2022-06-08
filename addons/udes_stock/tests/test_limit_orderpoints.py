"""Tests for the limit orderpoints flag."""

from odoo.exceptions import ValidationError
from . import common


class LimitOrderpointsTestCase(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(LimitOrderpointsTestCase, cls).setUpClass()

        # Setup an output location, parent and grandparent
        Location = cls.env["stock.location"]
        cls.op_warehouse_location = Location.create({"name": "UPL"})
        cls.op_out_location = cls.picking_type_pick.default_location_dest_id.copy(
            {
                "name": "TEST_OUT",
                "active": True,
                "location_id": cls.op_warehouse_location.id,
            }
        )
        cls.op_test_output_location_01 = Location.create(
            {
                "name": "Test output location 01",
                "barcode": "LTESTOUT01",
                "location_id": cls.op_out_location.id,
            }
        )

        # Create an orderpoint with values
        cls.create_orderpoint(cls.apple, cls.op_test_output_location_01, 5, 10)

    def test01_cannot_add_orderpoint_if_one_exists(self):
        """Tests cannot add an orderpoint if one already exists and the limit
        orderpoints flag is set on the location.
        """
        self.op_test_output_location_01.u_limit_orderpoints = True
        with self.assertRaises(ValidationError) as cm:
            self.create_orderpoint(self.banana, self.op_test_output_location_01, 5, 10)
        ex = cm.exception
        self.assertEqual(
            f"An order point for location {self.op_test_output_location_01.name} "
            f"already exists on {self.apple.name}",
            ex.args[0],
        )

    def test02_cannot_add_orderpoint_if_limit_on_parent(self):
        """Tests cannot add an orderpoint if one already exists and the limit
        orderpoints flag is set on the location's parent location.
        """
        self.op_out_location.u_limit_orderpoints = True
        with self.assertRaises(ValidationError) as cm:
            self.create_orderpoint(self.banana, self.op_test_output_location_01, 5, 10)
        ex = cm.exception
        self.assertEqual(
            f"An order point for location {self.op_test_output_location_01.name} "
            f"already exists on {self.apple.name}",
            ex.args[0],
        )

    def test03_cannot_add_orderpoint_if_limit_on_grandparent(self):
        """Tests cannot add an orderpoint if one already exists and the limit
        orderpoints flag is set on the location's grandparent location.
        """
        self.op_warehouse_location.u_limit_orderpoints = True
        with self.assertRaises(ValidationError) as cm:
            self.create_orderpoint(self.banana, self.op_test_output_location_01, 5, 10)
        ex = cm.exception
        self.assertEqual(
            f"An order point for location {self.op_test_output_location_01.name} "
            f"already exists on {self.apple.name}",
            ex.args[0],
        )
