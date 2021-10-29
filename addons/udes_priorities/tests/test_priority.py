# -*- coding: utf-8 -*-
from . import common
from odoo.exceptions import AccessError, UserError, ValidationError


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
            self.assertEqual(
                retrieved, ordered, "Incorrect ordering after being modified"
            )

    def test_check_other_user_rights_for_priorities(self):
        """
        Check that non trusted or non admin users cannot modify priorities.
        """
        with self.assertRaises(UserError):
            self.urgent.sudo(self.simple_stock_usr).reference = "This is not allowed"

        with self.assertRaises(AccessError):
            self.urgent.sudo(self.simple_stock_usr).description = "This is not allowed"

        with self.assertRaises(UserError):
            self.urgent.sudo(self.simple_stock_usr).active = False

        with self.assertRaises(UserError):
            self.urgent.sudo(self.simple_stock_usr).unlink()

    def test_check_editable_fields_for_priorities(self):
        """
        Check that the correct users can modify specific fields.
        """
        self.urgent.name = "This is allowed1"
        self.urgent.sudo(self.trusted_usr).name = "This is allowed2"

        self.urgent.description = "This is allowed1"
        self.urgent.sudo(self.trusted_usr).description = "This is allowed2"

        with self.assertRaises(UserError):
            self.urgent.reference = "This is not allowed"
        with self.assertRaises(UserError):
            self.urgent.sudo(self.trusted_usr).reference = "This is not allowed"

        self.urgent.sudo(self.trusted_usr).sequence = "3"

        self.urgent.sudo(self.trusted_usr).active = False
        self.urgent.sudo(self.trusted_usr).active = True

        self.urgent.sudo(self.trusted_usr).picking_type_ids += self.picking_type_pick

    def test_cannot_remove_picking_type_with_assigned_transfers(self):
        picking1 = self.create_picking(self.picking_type_pick)
        picking1.priority = self.urgent.reference

        with self.assertRaises(UserError):
            self.urgent.picking_type_ids -= self.picking_type_pick

    def test_cannot_archive_picking_type_with_assigned_transfers(self):
        picking1 = self.create_picking(self.picking_type_pick)
        picking1.priority = self.urgent.reference

        with self.assertRaises(ValidationError):
            self.urgent.active = False

    def test_cannot_remove_priority_with_assigned_transfers(self):
        picking1 = self.create_picking(self.picking_type_pick)
        picking1.priority = self.urgent.reference

        with self.assertRaises(UserError):
            self.urgent.unlink()
