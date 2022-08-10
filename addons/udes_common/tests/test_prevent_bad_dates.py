"""Tests for preventing invalid dates on backend"""

from odoo.exceptions import UserError
from odoo.tests import common, tagged


@tagged("post_install")
class TestPreventBadDates(common.SavepointCase):
    """Tests for raising error if date is a year earlier than 1000"""

    @classmethod
    def setUpClass(cls):
        super(TestPreventBadDates, cls).setUpClass()

    def test_date_is_allowed(self):
        """Test that partner can be created and modified if date entered after year 1000"""
        ResPartner = self.env["res.partner"]

        self.successful_partner = ResPartner.create(
            dict(
                name="Partner Test",
                date="1001-01-01",
            )
        )
        self.successful_partner.write(
            dict(
                date="1000-01-02",
            )
        )

    def test_prevent_bad_date(self):
        """Test that partner can not be created and modified if date
        entered is earlier than year 1000"""
        ResPartner = self.env["res.partner"]

        with self.assertRaises(UserError, msg="Date 0972-01-01 is not valid."), self.cr.savepoint():
            self.unsuccessful_partner = ResPartner.create(
                dict(
                    name="Partner Test 2",
                    date="0972-01-01",
                )
            )
        self.successful_partner_2 = ResPartner.create(
            dict(
                name="Partner Test 3",
                date="1001-01-01",
            )
        )
        with self.assertRaises(UserError, msg="Date 0980-01-02 is not valid."), self.cr.savepoint():
            self.successful_partner_2.write(
                dict(
                    date="0980-01-02",
                )
            )
