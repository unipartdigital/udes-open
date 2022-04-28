from . import common


class TestUserAssignments(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # TODO - Fix to be outbound_user and inbound_user when users are implemented
        cls.inbound_user = cls.env["res.users"].search([("login", "=", "admin")])
        cls.inbound_user_2 = cls.inbound_user.copy(
            {"name": "Inbound User 2", "login": "inbound_user_2_login"}
        )
        cls.inbound_user_3 = cls.inbound_user.copy(
            {"name": "Inbound User 3", "login": "inbound_user_3_login"}
        )
        cls.outbound_user = cls.inbound_user.copy(
            {"name": "Outbound User", "login": "outbound_user_login"}
        )

        # Create assigned goods in and putaway pickings
        # Different products to avoid refactoring and make filtering sensible
        cls.goods_in_picking = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=[{"product": cls.banana, "qty": 10}],
            assign=True,
        )
        product_info = {"product": cls.apple, "qty": 10}

        # Create quants
        cls.create_quant(product_info["product"].id, cls.received_location.id, product_info["qty"])
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
        user = self.inbound_user
        self.assertFalse(user.u_picking_assigned_time)
        self.assertFalse(user.u_picking_id)
        banana_products_info = [{"product": self.banana, "uom_qty": 1}]

        self.create_move(self.goods_in_picking, banana_products_info)
        self.assertEqual(self.goods_in_picking.state, "draft")
        user.assign_picking_to_users(self.goods_in_picking)
        # Assert not assigned
        self.assertFalse(user.u_picking_assigned_time)
        self.assertFalse(user.u_picking_id)

    def test_user_assignment_fail_due_to_done(self):
        """
        Test cannot assign a user when the picking is in state done
        """
        # Check the inbound User
        current_user = self.inbound_user
        self.assertFalse(current_user.u_picking_assigned_time)
        self.assertFalse(current_user.u_picking_id)

        # Assign picking to Inbound User
        current_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(current_user.u_picking_id, self.goods_in_picking)
        self.update_move_lines(self.goods_in_picking.move_line_ids, user=current_user)
        self.goods_in_picking.with_env(self.env(user=current_user))._action_done()
        self.assertEqual(self.goods_in_picking.state, "done")

        # Try to assign to another user
        new_user = self.inbound_user_2
        self.assertFalse(new_user.u_picking_id)
        new_user.assign_picking_to_users(self.goods_in_picking)
        # Assert not assigned
        self.assertFalse(new_user.u_picking_assigned_time)
        self.assertFalse(new_user.u_picking_id)

    def test_user_assignment_fail_due_to_cancel(self):
        """
        Test cannot assign a user when the picking is in state cancel
        """
        self.assertFalse(self.inbound_user.u_picking_assigned_time)
        self.assertFalse(self.inbound_user.u_picking_id)
        self.goods_in_picking.action_cancel()
        self.assertEqual(self.goods_in_picking.state, "cancel")
        self.inbound_user.assign_picking_to_users(self.goods_in_picking)
        # Assert not assigned
        self.assertFalse(self.inbound_user.u_picking_assigned_time)
        self.assertFalse(self.inbound_user.u_picking_id)

    def test_simple_assign_a_user(self):
        """Assign a user through assign_picking_to_users method"""
        self.assertFalse(self.inbound_user.u_picking_id)
        self.inbound_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.inbound_user.u_picking_id, self.goods_in_picking)

    def test_multiple_user_assignment_on_same_picking_fail(self):
        """
        Test if u_multi_users_enabled is not enabled, multiple users cannot be assigned
        to the same picking.
        """
        self.picking_type_goods_in.u_multi_users_enabled = False
        users = self.inbound_user | self.inbound_user_2 | self.inbound_user_3
        self.assertEqual(self.goods_in_picking.state, "assigned")

        # Assert nothing currently assigned
        for user in users:
            with self.subTest(user=user.name):
                self.assertFalse(user.u_picking_id)

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
        users = self.inbound_user | self.inbound_user_2 | self.inbound_user_3
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
        user = self.inbound_user
        self.assertEqual(self.goods_in_picking.state, "assigned")

        # Assert nothing currently assigned
        self.assertFalse(user.u_picking_id)

        # Manually assign a user to the picking
        user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(user.u_picking_id, self.goods_in_picking)
        user_start_time = user.u_picking_assigned_time
        picking_start_time = self.goods_in_picking.u_date_started

        # Assign another user to the picking
        user_2 = self.inbound_user_2
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
        self.inbound_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.inbound_user.u_picking_id, self.goods_in_picking)
        self.assertTrue(self.inbound_user.u_picking_assigned_time)
        # Try to assign the same picking
        start_time = self.inbound_user.u_picking_assigned_time
        self.inbound_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.inbound_user.u_picking_id, self.goods_in_picking)
        self.assertEqual(start_time, self.inbound_user.u_picking_assigned_time)

    def test_unassign_user_with_u_multi_users_enabled(self):
        """Test un assignment of a picking when multiple users can exist on it"""
        self.picking_type_goods_in.u_multi_users_enabled = True
        user = self.inbound_user
        # Manually assign a user to the picking
        user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(user.u_picking_id, self.goods_in_picking)
        user.unassign_pickings_from_users()
        self.assertFalse(user.u_picking_id)

    def test_unassign_multiple_users(self):
        """Test that all users are un assigned from their pickings"""
        # Manually assign a user to the picking
        self.inbound_user.assign_picking_to_users(self.goods_in_picking)
        self.inbound_user_2.assign_picking_to_users(self.putaway_picking)
        self.outbound_user.assign_picking_to_users(self.pick_picking)
        self.assertEqual(self.inbound_user.u_picking_id, self.goods_in_picking)
        self.assertEqual(self.inbound_user_2.u_picking_id, self.putaway_picking)
        self.assertEqual(self.outbound_user.u_picking_id, self.pick_picking)

        users = self.inbound_user | self.inbound_user_2 | self.outbound_user
        users.unassign_pickings_from_users()
        self.assertFalse(self.inbound_user.u_picking_id)
        self.assertFalse(self.inbound_user_2.u_picking_id)
        self.assertFalse(self.outbound_user.u_picking_id)

    def test_user_gets_unassigned_from_other_pickings(self):
        """
        When a user gets assigned a picking, then swaps pickings, make
        sure the original picking becomes un assigned.
        """
        self.inbound_user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.inbound_user.u_picking_id, self.goods_in_picking)
        self.assertEqual(
            self.goods_in_picking.u_date_started, self.inbound_user.u_picking_assigned_time
        )
        # Assign the second picking
        self.inbound_user.assign_picking_to_users(self.putaway_picking)
        # Assert the user has updated picking information
        self.assertEqual(self.putaway_picking, self.inbound_user.u_picking_id)
        self.assertEqual(
            self.putaway_picking.u_date_started, self.inbound_user.u_picking_assigned_time
        )

    def test_unassign_with_skip_users(self):
        """Test that if the skip_users flag is passed, the user will still be assigned"""
        self.picking_type_goods_in.u_multi_users_enabled = True
        # Manually assign a user to the picking
        user = self.inbound_user
        user.assign_picking_to_users(self.goods_in_picking)
        self.assertEqual(self.goods_in_picking.u_assigned_user_ids, user)
        user_start_time = user.u_picking_assigned_time

        self.goods_in_picking.unassign_users(skip_users=user)
        self.assertTrue(user.u_picking_id)
        self.assertEqual(self.goods_in_picking.u_assigned_user_ids, user)
        self.assertEqual(user.u_picking_id, self.goods_in_picking)
        self.assertEqual(user.u_picking_assigned_time, user_start_time)
