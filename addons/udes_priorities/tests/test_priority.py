# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import UserError


class TestPriorities(common.BasePriorities):
    def test_priority_ordering(self):
        Priorities = self.env["udes_priorities.priority"]

        # Test default ordering
        correct_order = [
            self.urgent,
            self.normal,
            self.not_urgent,
        ]

        actual_order = Priorities.search([("id", "in", self.test_priorities.ids)])

        for retrieved, ordered in zip(actual_order, correct_order):
            self.assertEqual(retrieved, ordered, "Incorrect ordering")

        # Modify ordering
        new_order = list(reversed(correct_order))

        for i, rec in enumerate(new_order):
            rec.sequence = i

        actual_order_2 = Priorities.search([("id", "in", self.test_priorities.ids)])
        for retrieved, ordered in zip(actual_order_2, new_order):
            self.assertEqual(retrieved, ordered, "Incorrect ordering after being modified")

    def test_outstanding_picking(self):
        self.urgent.reference = "This is allowed"

        picking = self.create_picking(self.picking_type_pick)
        with self.assertRaises(
            UserError, msg="Allowed to change reference while there is outstanding an picking"
        ):
            self.urgent.reference = "This is not allowed"

        self.urgent.description = "This is still allowed"

        with self.assertRaises(
            UserError, msg="Allowed to unlink while there is outstanding an picking"
        ):
            self.urgent.unlink()
