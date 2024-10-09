"""Unit tests for PreciseDatetime field."""

import datetime as dt

from odoo import fields, models
from odoo.fields import Datetime
from odoo.tests.common import SavepointCase, tagged

from ..models.fields import PreciseDatetime


@tagged("post_install", "-at_install")
class PreciseDatetimeTestCase(SavepointCase):
    """Tests for the PreciseDatetime field type."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()

        # Create a test model scoped to this testcase.

        class TestModel(models.Model):
            _name = "udes_common.test_model"
            _description = "PreciseDatetime Field Test Model."

            imprecise = Datetime()
            precise = PreciseDatetime()

        TestModel._build_model(cls.registry, cls.env.cr)
        cls.addClassCleanup(cls.registry.__delitem__, TestModel._name)

        cls.registry.setup_models(cls.env.cr)
        cls.registry.init_models(
            cls.env.cr,
            ["udes_common.test_model"],
            dict(module="udes_common", update_custom_fields=True),
        )

        # Expose the registry model to test methods.
        cls.TestModel = cls.env["udes_common.test_model"]
