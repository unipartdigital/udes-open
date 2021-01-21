# -*- coding: utf-8 -*-

import time

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import common


@common.at_install(False)
@common.post_install(True)
class TestPasswordManager(common.TransactionCase):
    """
    Check that Password Managers can update the password of other users,
    including admin/debug users if they are also a debug user.
    """

    def setUp(self):
        """Create users for testing"""
        super(TestPasswordManager, self).setUp()
        self._setup_test_users()
        # Amount of seconds to wait before updating password
        # This is done to ensure the `password_write_date` can be used to verify
        # if a user's password was updated
        self.password_wait_interval = 2

    def _setup_test_users(self):
        """
        Create the following users:

        1. Password Manager
        2. Debug User
        3. Standard User (default permissions)
        """
        self.group_password_manager = self.env.ref("udes_security.group_password_manager")
        self.group_debug_user = self.env.ref("udes_security.group_debug_user")

        self.password_manager = self.create_user("Password Manager", self.group_password_manager)
        self.debug_user = self.create_user("Debug User", self.group_debug_user)
        self.standard_user = self.create_user("Standard User")

        self.all_users = self.password_manager | self.debug_user | self.standard_user

    def create_user(self, name, groups=None, **kwargs):
        """
        Create and return a user record

        :args:
            - name: String for the name of the user
            - groups: Recordset of `res.groups` to apply to the user,
                      if None only the default groups will be used
        """
        User = self.env["res.users"]

        login = name.lower().replace(" ", "_")
        user_vals = {"name": name, "login": login}

        if groups:
            user_vals["groups_id"] = [(6, 0, groups.ids)]

        user_vals.update(kwargs)

        return User.create(user_vals)

    def add_group_to_user(self, user, groups):
        """
        Add supplied groups to user

        :args:
            - user: Recordset of `res.users`
            - groups: Recordset of `res.groups` to apply to the user
        """
        new_group_vals = [(4, group.id) for group in groups]

        user.write(
            {"groups_id": new_group_vals,}
        )

    def change_user_password_as_user(self, sudo_user, users_to_update, new_password=None):
        """
        As supplied `sudo_user`, change the password of each user in `users_to_update`.
        
        Will raise an AccessError if sudo_user doesn't have permission to
        change the password of any user in `users_to_update`.

        :args:
            - sudo_user: Singleton `res.users` record to carry out the change as
            - users_to_update: Recordset of `res.users` to change password for
            - new_password: Password to set each user in `users_to_update`, 
                            value will be generated if None supplied
        """
        ChangePwdWiz = self.env["change.password.wizard"]

        sudo_user.ensure_one()
        # Carry out operation as specified sudo user
        ChangePwdWiz = ChangePwdWiz.sudo(sudo_user)

        if new_password is None:
            new_password = "UnitTestUserPassword123!"

        change_pwd_user_vals = [
            (0, 0, {"user_id": user.id, "user_login": user.login, "new_passwd": new_password})
            for user in users_to_update
        ]
        change_pwd_wiz = ChangePwdWiz.create({"user_ids": change_pwd_user_vals})
        time.sleep(self.password_wait_interval)
        change_pwd_wiz.change_password_button()

    def assertUserPasswordUpdated(self, sudo_user, users_to_update, new_password=None):
        """
        Assert that each user in `users_to_update` had their password updated by checking the
        date it was last updated.
        """
        time_before_update = fields.Datetime.now()
        self.change_user_password_as_user(sudo_user, users_to_update, new_password=new_password)
        for user in users_to_update:
            self.assertGreater(
                user.password_write_date,
                time_before_update,
                f"Password for user '{user.name}' should have been updated",
            )

    def assertUserPasswordNotUpdated(self, sudo_user, users_to_update, new_password=None):
        """
        Assert that no user in `users_to_update` had their password updated by checking the
        date it was last updated.

        Also assert that an AccessError was raised.
        """
        time_before_update = fields.Datetime.now()

        with self.assertRaises(AccessError):
            self.change_user_password_as_user(sudo_user, users_to_update, new_password=new_password)

        for user in users_to_update:
            self.assertLessEqual(
                user.password_write_date,
                time_before_update,
                f"Password for user '{user.name}' should not have been updated",
            )

    def test_assert_all_users_can_update_own_password(self):
        """
        Assert that standard, debug and password manager users can all update their own passwords
        """
        # Each user should be able to update their own password, regardless of permissions
        for user in self.all_users:
            self.assertUserPasswordUpdated(user, user)

    def test_assert_standard_user_cannot_update_other_users_passwords(self):
        """
        Assert that standard user cannot update another user's password
        """
        # Standard user should not be able to update passsword manager's password
        self.assertUserPasswordNotUpdated(self.standard_user, self.password_manager)

    def test_assert_password_manager_can_update_standard_users_password(self):
        """
        Assert that password manager is able to update standard user's password
        """
        # Standard user should not be able to update passsword manager's password
        self.assertUserPasswordUpdated(self.password_manager, self.standard_user)

    def test_assert_password_manager_cannot_update_debug_users_password(self):
        """
        Assert that password manager cannot update debug user's password
        """
        # Password manager should not be able to change debug user's password
        self.assertUserPasswordNotUpdated(self.password_manager, self.debug_user)

    def test_assert_debug_user_cannot_update_other_users_passwords(self):
        """
        Assert that debug user cannot update other user's password
        """
        # Debug user should not be able to change other user's password as it doesn't have the
        # password manager group
        self.assertUserPasswordNotUpdated(self.debug_user, self.standard_user)

    def test_assert_debug_user_with_password_manager_can_update_other_debug_users_passwords(self):
        """
        Assert that debug user with password manager group can update other debug user's password
        """
        # Make existing debug user password manager
        self.add_group_to_user(self.debug_user, self.group_password_manager)

        # Create new debug user
        new_debug_user = self.create_user("New Debug User", self.group_debug_user)

        # Debug user with password manager permission should be able to update password of other
        # debug users
        self.assertUserPasswordUpdated(self.debug_user, new_debug_user)
