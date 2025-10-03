"""Tests for the limit orderpoints flag."""

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger
from psycopg2.errors import CheckViolation

from . import common
from odoo.addons.udes_common.tests.common import SavepointMixin


class LimitOrderpointsTestCase(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(LimitOrderpointsTestCase, cls).setUpClass()

        # Setup an output location, parent and grandparent
        cls.op_warehouse_location = cls.create_location("UPL", usage="view")
        cls.op_out_location = cls.picking_type_pick.default_location_dest_id.copy(
            {
                "name": "TEST_OUT",
                "active": True,
                "location_id": cls.op_warehouse_location.id,
                "usage": "view",
            }
        )
        cls.op_test_output_location_01 = cls.create_location(
            "Test output location 01", barcode="LTESTOUT01", location_id=cls.op_out_location.id
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
            f"already exists on {self.apple.name}.",
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
            f"already exists on {self.apple.name}.",
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
            f"already exists on {self.apple.name}.",
            ex.args[0],
        )


class ProductQuantityTestCase(common.BaseUDES, SavepointMixin):
    """Unit tests for product quantities."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cubic_metre_uom = cls.env.ref("uom.product_uom_cubic_meter")
        cls.mercury = cls.create_product(
            "mercury", uom_id=cubic_metre_uom.id, uom_po_id=cubic_metre_uom.id
        )

    def test_cannot_create_orderpoint_with_zero_minimum_quantity(self):
        """The system will reject reorder rules if the minimum quantity is not positive."""
        min_qtys = [0, -1]
        for min_qty in min_qtys:
            with (
                self.subTest(min_qty=min_qty),
                self.savepoint(),
                mute_logger("odoo.sql_db"),
                self.assertRaises(CheckViolation),
            ):
                self.create_orderpoint(self.apple, self.test_stock_location_01, min_qty, 10)

    def test_cannot_amend_orderpoint_to_have_zero_minimum_quantity(self):
        """The system will reject reorder rules if the minimum quantity is not positive."""
        orderpoint = self.create_orderpoint(self.apple, self.test_stock_location_01, 1, 10)
        min_qtys = [0, -1]
        for min_qty in min_qtys:
            with (
                self.subTest(min_qty=min_qty),
                self.savepoint(),
                mute_logger("odoo.sql_db"),
                self.assertRaises(CheckViolation),
            ):
                orderpoint.product_min_qty = min_qty

    def test_can_create_orderpoint_with_minimum_quantity_between_zero_and_one(self):
        """The system will create reorder rules with fractional minimum quantities."""
        op = self.create_orderpoint(self.mercury, self.test_stock_location_01, 0.01, 10)

        self.assertEqual(op.product_min_qty, 0.01)
