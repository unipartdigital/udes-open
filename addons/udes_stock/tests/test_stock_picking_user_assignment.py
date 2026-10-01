from unittest.mock import patch

from odoo.tests import Form
from odoo.tools import mute_logger

from . import common


class TestUserAssignments(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.stock_user = cls.create_user(
            "stock user",
            "stock user",
            groups_id=[(6, 0, [cls.env.ref("stock.group_stock_user").id])],
        )
        cls.stock_user_2 = cls.stock_user.copy(
            {"name": "Stock User 2", "login": "stock_user_2_login"}
        )
        cls.stock_user_3 = cls.stock_user.copy(
            {"name": "Stock User 3", "login": "stock_user_3_login"}
        )
        cls.stock_user_4 = cls.stock_user.copy(
            {"name": "Stock User 4", "login": "stock_user_4_login"}
        )

        # Create assigned goods in and putaway pickings
        # Different products to avoid refactoring and make filtering sensible
        cls.goods_in_picking = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=[{"product": cls.banana, "qty": 10}],
            assign=True,
        )
        cls.goods_in_picking.move_line_ids.location_dest_id = cls.test_received_location_01
        product_info = {"product": cls.apple, "qty": 10}

        # Create quants
        cls.create_quant(
            product_info["product"].id, cls.test_received_location_01.id, product_info["qty"]
        )
        cls.create_quant(
            product_info["product"].id, cls.test_stock_location_01.id, product_info["qty"]
        )

        cls.putaway_picking = cls.create_picking(
            cls.picking_type_putaway, products_info=[product_info], assign=True
        )
        cls.pick_picking = cls.create_picking(
            cls.picking_type_pick, products_info=[product_info], assign=True
        )

    def test_user_assignment_fail_due_to_draft(self):
        """
        Test cannot assign a user when the picking is in state draft
        """
        user = self.stock_user
        self.assertFalse(user.u_picking_assigned_time)
        self.assertFalse(user.u_picking_id)
        banana_products_info = [{"product": self.banana, "uom_qty": 1}]

        self.create_move(self.goods_in_picking, banana_products_info)
        self.assertEqual(self.goods_in_picking.state, "draft")
        with mute_logger("odoo.addons.udes_stock.models.res_users"):
            user.assign_picking_to_users(self.goods_in_picking)
        # Assert not assigned
        self.assertFalse(user.u_picking_assigned_time)
        self.assertFalse(user.u_picking_id)

    def test_user_assignment_fail_due_to_done(self):
        """
        Test cannot assign a user when the picking is in state done
        """
        # Check the inbound User
        current_user = self.stock_user
        self.assertFalse(current_user.u_picking_assigned_time)
        self.assertFalse(current_user.u_picking_id)

        # Assign picking to Inbound User
        current_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(current_user.u_picking_id, self.goods_in_picking)
        self.update_move_lines(self.goods_in_picking.move_line_ids, user=current_user)
        self.goods_in_picking.with_env(self.env(user=current_user))._action_done()
        self.assertEqual(self.goods_in_picking.state, "done")

        # Try to assign to another user
        new_user = self.stock_user_2
        self.assertFalse(new_user.u_picking_id)
        with mute_logger("odoo.addons.udes_stock.models.res_users"):
            new_user.assign_picking_to_users(self.goods_in_picking)
        # Assert not assigned
        self.assertFalse(new_user.u_picking_assigned_time)
        self.assertFalse(new_user.u_picking_id)

    def test_user_assignment_fail_due_to_cancel(self):
        """
        Test cannot assign a user when the picking is in state cancel
        """
        self.assertFalse(self.stock_user.u_picking_assigned_time)
        self.assertFalse(self.stock_user.u_picking_id)
        self.goods_in_picking.action_cancel()
        self.assertEqual(self.goods_in_picking.state, "cancel")
        with mute_logger("odoo.addons.udes_stock.models.res_users"):
            self.stock_user.assign_picking_to_users(self.goods_in_picking)
        # Assert not assigned
        self.assertFalse(self.stock_user.u_picking_assigned_time)
        self.assertFalse(self.stock_user.u_picking_id)

    def test_simple_assign_a_user(self):
        """Assign a user through assign_picking_to_users method"""
        self.assertFalse(self.stock_user.u_picking_id)
        self.stock_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.stock_user.u_picking_id, self.goods_in_picking)

    def test_multiple_user_assignment_on_same_picking_fail(self):
        """
        Test if u_multi_users_enabled is not enabled, multiple users cannot be assigned
        to the same picking.
        """
        self.picking_type_goods_in.u_multi_users_enabled = False
        users = self.stock_user | self.stock_user_2 | self.stock_user_3
        self.assertEqual(self.goods_in_picking.state, "assigned")

        # Assert nothing currently assigned
        for user in users:
            with self.subTest(user=user.name):
                self.assertFalse(user.u_picking_id)

        with mute_logger("odoo.addons.udes_stock.models.res_users"):
            # Manually assign a user to the picking
            users.assign_picking_to_users(self.goods_in_picking)
            for user in users:
                with self.subTest(user=user.name):
                    self.assertFalse(user.u_picking_id)

    def test_multiple_user_assignment_on_same_picking_success(self):
        """
        Test if u_multi_users_enabled is enabled, multiple users can be assigned
        the same picking.
        """
        self.picking_type_goods_in.u_multi_users_enabled = True
        users = self.stock_user | self.stock_user_2 | self.stock_user_3
        self.assertEqual(self.goods_in_picking.state, "assigned")

        # Assert nothing currently assigned
        for user in users:
            with self.subTest(user=user.name):
                self.assertFalse(user.u_picking_id)

        # Manually assign a user to the picking
        users.assign_picking_to_users(self.goods_in_picking)
        for user in users:
            with self.subTest(user=user.name):
                self.assertEqual(user.u_picking_id, self.goods_in_picking)

    def test_assign_additional_user_to_picking_with_u_multi_users_enabled(self):
        """
        Test if u_multi_users_enabled is enabled, another user can be assigned
        """
        self.picking_type_goods_in.u_multi_users_enabled = True
        user = self.stock_user
        self.assertEqual(self.goods_in_picking.state, "assigned")

        # Assert nothing currently assigned
        self.assertFalse(user.u_picking_id)

        # Manually assign a user to the picking
        user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(user.u_picking_id, self.goods_in_picking)
        user_start_time = user.u_picking_assigned_time
        picking_start_time = self.goods_in_picking.u_date_started

        # Assign another user to the picking
        user_2 = self.stock_user_2
        user_2.assign_picking_to_users(self.goods_in_picking)

        self.assertEqual(picking_start_time, self.goods_in_picking.u_date_started)
        self.assertEqual(user.u_picking_id, self.goods_in_picking)
        self.assertEqual(user.u_picking_assigned_time, user_start_time)
        self.assertEqual(user_2.u_picking_id, self.goods_in_picking)
        self.assertGreater(user_2.u_picking_assigned_time, user_start_time)

    def test_try_assign_user_to_already_assigned_picking(self):
        """
        Test to check that a user is not re-assigned if they are already assigned to it.
        """
        self.assertEqual(self.goods_in_picking.state, "assigned")

        # Manually assign a user to the picking
        self.stock_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.stock_user.u_picking_id, self.goods_in_picking)
        self.assertTrue(self.stock_user.u_picking_assigned_time)
        # Try to assign the same picking
        start_time = self.stock_user.u_picking_assigned_time
        self.stock_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.stock_user.u_picking_id, self.goods_in_picking)
        self.assertEqual(start_time, self.stock_user.u_picking_assigned_time)

    def test_unassign_user_with_u_multi_users_enabled(self):
        """Test un assignment of a picking when multiple users can exist on it"""
        self.picking_type_goods_in.u_multi_users_enabled = True
        user = self.stock_user
        # Manually assign a user to the picking
        user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(user.u_picking_id, self.goods_in_picking)
        user.unassign_pickings_from_users()
        self.assertFalse(user.u_picking_id)

    def test_unassign_multiple_users(self):
        """Test that all users are un assigned from their pickings"""
        # Manually assign a user to the picking
        self.stock_user.assign_picking_to_users(self.goods_in_picking)
        self.stock_user_2.assign_picking_to_users(self.putaway_picking)
        self.stock_user_4.assign_picking_to_users(self.pick_picking)
        self.assertEqual(self.stock_user.u_picking_id, self.goods_in_picking)
        self.assertEqual(self.stock_user_2.u_picking_id, self.putaway_picking)
        self.assertEqual(self.stock_user_4.u_picking_id, self.pick_picking)

        users = self.stock_user | self.stock_user_2 | self.stock_user_4
        users.unassign_pickings_from_users()
        self.assertFalse(self.stock_user.u_picking_id)
        self.assertFalse(self.stock_user_2.u_picking_id)
        self.assertFalse(self.stock_user_4.u_picking_id)

    def test_user_gets_unassigned_from_other_pickings(self):
        """
        When a user gets assigned a picking, then swaps pickings, make
        sure the original picking becomes un assigned.
        """
        self.stock_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.stock_user.u_picking_id, self.goods_in_picking)
        self.assertEqual(
            self.goods_in_picking.u_date_started, self.stock_user.u_picking_assigned_time
        )
        # Assign the second picking
        self.stock_user.assign_picking_to_users(self.putaway_picking)
        # Assert the user has updated picking information
        self.assertEqual(self.putaway_picking, self.stock_user.u_picking_id)
        self.assertEqual(
            self.putaway_picking.u_date_started, self.stock_user.u_picking_assigned_time
        )

    def test_unassign_with_skip_users(self):
        """Test that if the skip_users flag is passed, the user will still be assigned"""
        self.picking_type_goods_in.u_multi_users_enabled = True
        # Manually assign a user to the picking
        user = self.stock_user
        user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.goods_in_picking.u_assigned_user_ids, user)
        user_start_time = user.u_picking_assigned_time

        self.goods_in_picking.unassign_users(skip_users=user)
        self.assertTrue(user.u_picking_id)
        self.assertEqual(self.goods_in_picking.u_assigned_user_ids, user)
        self.assertEqual(user.u_picking_id, self.goods_in_picking)
        self.assertEqual(user.u_picking_assigned_time, user_start_time)


class TestButtonValidateUserAssignment(common.BaseUDES):
    """Test that the validating user is assigned to the pickings while they are done"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.stock_user = cls.create_user(
            "stock user",
            "stock user",
            groups_id=[(6, 0, [cls.env.ref("stock.group_stock_user").id])],
        )
        cls.stock_user_2 = cls.stock_user.copy(
            {"name": "Stock User 2", "login": "stock_user_2_login"}
        )

        cls.goods_in_picking = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=[{"product": cls.banana, "qty": 10}],
            assign=True,
        )
        cls.goods_in_picking.move_line_ids.location_dest_id = cls.test_received_location_01
        cls.goods_in_picking_2 = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=[{"product": cls.fig, "qty": 5}],
            assign=True,
        )
        cls.goods_in_picking_2.move_line_ids.location_dest_id = cls.test_received_location_01


    def setUp(self):
        """
        Spy on the user assignment methods, recording each picking (and its state) the
        users were assigned to when getting unassigned from it.
        """
        super().setUp()
        ResUsers = type(self.env["res.users"])
        original_unassign = ResUsers.unassign_pickings_from_users
        original_assign = ResUsers.assign_picking_to_users

        self.unassigned_from = []
        self.assign_calls = 0
        test = self

        def unassign_pickings_from_users(users, *args, **kwargs):
            for user in users.filtered("u_picking_id"):
                test.unassigned_from.append((user, user.u_picking_id, user.u_picking_id.state))
            return original_unassign(users, *args, **kwargs)

        def assign_picking_to_users(users, *args, **kwargs):
            test.assign_calls += 1
            return original_assign(users, *args, **kwargs)

        for name, spy in (
            ("unassign_pickings_from_users", unassign_pickings_from_users),
            ("assign_picking_to_users", assign_picking_to_users),
        ):
            patcher = patch.object(ResUsers, name, spy)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _as_stock_user(self, records):
        return records.with_user(self.stock_user).sudo()

    def _process_wizard(self, action, method="process"):
        """Process the pre-validation wizard returned by button_validate, as the stock user"""
        Wizard = self._as_stock_user(self.env[action["res_model"]])
        wizard = Form(Wizard.with_context(action["context"])).save()
        return getattr(wizard, method)()

    def test_button_validate_assigns_validating_user_while_done(self):
        """Test that the validating user is assigned while the picking is done, then unassigned"""
        picking = self.goods_in_picking
        self.update_move_lines(picking.move_line_ids)
        self.assertFalse(picking.u_date_started)

        res = self._as_stock_user(picking).button_validate()

        self.assertIs(res, True)
        self.assertEqual(picking.state, "done")
        self.assertEqual(self.unassigned_from, [(self.stock_user, picking, "done")])
        self.assertFalse(self.stock_user.u_picking_id)
        self.assertTrue(picking.u_date_started)

    def test_button_validate_unassigns_users_already_working_on_picking(self):
        """Test that users already working on the picking get unassigned when validating"""
        picking = self.goods_in_picking
        self.stock_user_2.assign_picking_to_users(picking)
        self.update_move_lines(picking.move_line_ids)

        self._as_stock_user(picking).button_validate()

        self.assertEqual(picking.state, "done")
        self.assertFalse(self.stock_user_2.u_picking_id)
        self.assertFalse(self.stock_user.u_picking_id)
        self.assertIn((self.stock_user, picking, "done"), self.unassigned_from)

    def test_button_validate_with_immediate_transfer_wizard(self):
        """
        Test that the validating user is only assigned when the immediate transfer wizard is
        processed, not when it is created.
        """
        picking = self.goods_in_picking

        action = self._as_stock_user(picking).button_validate()

        self.assertEqual(action["res_model"], "stock.immediate.transfer")
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(self.assign_calls, 0)
        self.assertFalse(self.stock_user.u_picking_id)

        self._process_wizard(action, "process")

        self.assertEqual(picking.state, "done")
        self.assertEqual(self.assign_calls, 1)
        self.assertEqual(self.unassigned_from, [(self.stock_user, picking, "done")])

    def test_button_validate_with_backorder_wizard_creates_backorder(self):
        """
        Test that the validating user is assigned to the original picking while it is done
        when a backorder is created, and is not left assigned to the backorder.
        """
        picking = self.goods_in_picking
        self.update_move_lines(picking.move_line_ids, qty=4)

        action = self._as_stock_user(picking).button_validate()

        self.assertEqual(action["res_model"], "stock.backorder.confirmation")
        self.assertEqual(self.assign_calls, 0)

        self._process_wizard(action, "process")

        backorder = picking.backorder_ids
        self.assertEqual(picking.state, "done")
        self.assertEqual(len(backorder), 1)
        self.assertEqual(backorder.state, "assigned")
        self.assertEqual(self.assign_calls, 1)
        self.assertEqual(self.unassigned_from, [(self.stock_user, picking, "done")])
        self.assertFalse(self.stock_user.u_picking_id)

    def test_button_validate_with_backorder_wizard_no_backorder(self):
        """
        Test that the validating user is assigned to the picking while it is done when
        choosing not to create a backorder.
        """
        picking = self.goods_in_picking
        self.update_move_lines(picking.move_line_ids, qty=4)

        action = self._as_stock_user(picking).button_validate()
        self._process_wizard(action, "process_cancel_backorder")

        self.assertEqual(picking.state, "done")
        self.assertFalse(picking.backorder_ids)
        self.assertEqual(self.assign_calls, 1)
        self.assertEqual(self.unassigned_from, [(self.stock_user, picking, "done")])
        self.assertFalse(self.stock_user.u_picking_id)

    def test_button_validate_multiple_pickings(self):
        """Test that the validating user is assigned to each picking in turn while it is done"""
        pickings = self.goods_in_picking | self.goods_in_picking_2
        self.update_move_lines(pickings.move_line_ids)

        res = self._as_stock_user(pickings).button_validate()

        self.assertIs(res, True)
        self.assertEqual(pickings.mapped("state"), ["done", "done"])
        self.assertEqual(
            self.unassigned_from,
            [
                (self.stock_user, self.goods_in_picking, "done"),
                (self.stock_user, self.goods_in_picking_2, "done"),
            ],
        )
        self.assertFalse(self.stock_user.u_picking_id)

    def test_batch_action_done_assigns_validating_user(self):
        """
        Test that completing a batch assigns the validating user to each picking in turn
        while it is done.
        """
        pickings = self.goods_in_picking | self.goods_in_picking_2
        batch = self.create_batch(user=self.stock_user, picking_ids=[(6, 0, pickings.ids)])
        batch.action_confirm()
        self.update_move_lines(pickings.move_line_ids)

        self._as_stock_user(batch).action_done()

        self.assertEqual(pickings.mapped("state"), ["done", "done"])
        self.assertEqual(
            self.unassigned_from,
            [
                (self.stock_user, self.goods_in_picking, "done"),
                (self.stock_user, self.goods_in_picking_2, "done"),
            ],
        )
        self.assertFalse(self.stock_user.u_picking_id)

    def test_validate_picking_does_not_reassign_users(self):
        """
        Test that validating outside of button_validate (e.g. from the mobile) does not
        change which users are assigned to the picking.
        """
        picking = self.goods_in_picking
        self.stock_user_2.assign_picking_to_users(picking)
        self.assign_calls = 0
        self.update_move_lines(picking.move_line_ids)

        self._as_stock_user(picking).validate_picking()

        self.assertEqual(picking.state, "done")
        self.assertEqual(self.assign_calls, 0)
        self.assertEqual(self.unassigned_from, [])
        self.assertEqual(self.stock_user_2.u_picking_id, picking)
