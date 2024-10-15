"""Unit tests for PreciseDatetime field."""

import datetime as dt

from odoo import fields, models
from odoo.fields import Datetime
from odoo.tests.common import SavepointCase, tagged

from ..models.fields import PreciseDatetime


@tagged("post_install", "-at_install")
class PreciseDatetimeTestCase(SavepointCase):
    """Tests for the PreciseDatetime field type."""

    def test_now_returns_datetime_instance(self):
        """Our class should return type as the superclass."""
        imprecise_now = Datetime.now()
        precise_now = PreciseDatetime.now()

        self.assertTrue(isinstance(imprecise_now, dt.datetime))
        self.assertTrue(isinstance(precise_now, dt.datetime))

    def test_from_string_can_handle_microseconds(self):
        """The from string method should handle microseconds."""
        date_string = "2024-10-10 09:15:05.123"
        datetime_value = Datetime.from_string(date_string[:4])
        precise_datetime_value = PreciseDatetime.from_string(date_string)

        self.assertTrue(isinstance(datetime_value, dt.datetime))
        self.assertTrue(isinstance(precise_datetime_value, dt.datetime))
