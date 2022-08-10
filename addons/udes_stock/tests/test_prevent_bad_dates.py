"""Tests for preventing invalid dates on backend"""

from . import common
from odoo.exceptions import UserError


class TestPreventBadDates(common.BaseUDES):
    """Tests for raising error if date is a year earlier than 1000"""

    @classmethod
    def setUpClass(cls):
        super(TestPreventBadDates, cls).setUpClass()

    def test_date_is_allowed(self):
        """Test that a picking can be created and modified if date entered after year 1000"""
        self.successful_picking = self.create_picking(
            self.picking_type_in,
            origin="0001",
            scheduled_date="1001-01-01"
        )
        self.successful_picking.write(
            dict(
                scheduled_date="9999-12-31 17:00:30",
            )
        )

    def test_prevent_bad_date(self):
        """Test that picking can not be created and modified if date
        entered is earlier than year 1000"""

        with self.assertRaises(UserError, msg="Date 0972-01-01 is not valid."), self.cr.savepoint():
            self.unsuccessful_picking = self.create_picking(
                self.picking_type_in,
                origin="0002",
                scheduled_date="0972-01-01"
            )
        with self.assertRaises(UserError, msg="Date 10001-01-01 14:00:15 is not valid."), self.cr.savepoint():
            self.unsuccessful_picking_2 = self.create_picking(
                self.picking_type_in,
                origin="0003",
                scheduled_date="10001-01-01 14:00:15"
            )
        self.successful_picking_2 = self.create_picking(
            self.picking_type_in,
            origin="0004",
            scheduled_date="1001-01-01"
        )
        with self.assertRaises(UserError, msg="Date 0980-01-02 is not valid."), self.cr.savepoint():
            self.successful_picking_2.write(
                dict(
                    scheduled_date="0980-01-02",
                )
            )
        with self.assertRaises(UserError, msg="Date 10001-01-02 05:00:01 is not valid."), self.cr.savepoint():
            self.successful_picking_2.write(
                dict(
                    scheduled_date="10001-01-02 05:00:01",
                )
            )
