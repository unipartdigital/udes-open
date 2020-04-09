# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import common

@common.at_install(False)
@common.post_install(True)
class TestTrustedUser(common.SavepointCase):
    """
    Check that only the admin user can add and remove the Trusted User group
    """

    def setUp(self):
        """
        Create two users for testing
        """
        super(TestTrustedUser, self).setUp()

        User = self.env['res.users']

        self.group_access_rights = self.env.ref('base.group_erp_manager')
        self.group_trusted_user = self.env.ref(
                                      'udes_security.group_trusted_user')
        self.group_debug_user = self.env.ref(
                                      'udes_security.group_debug_user')

        self.user_1 = User.create({
            'name': 'Test User 1',
            'login': 'test_user_1',
            'groups_id': [(6, 0, [self.group_access_rights.id])],
        })
        self.user_2 = User.create({
            'name': 'Test User 2',
            'login': 'test_user_2',
        })

    def test01_trusted_add_remove_root(self):
        """Test that the admin user can add and remove the Trusted User group"""
        self._user_group_add_remove_root(self.group_trusted_user)

    def test02_debug_add_remove_root(self):
        """Test that the admin user can add and remove the Debug User group"""
        self._user_group_add_remove_root(self.group_debug_user)

    def test03_trusted_add_non_root(self):
        """Test that a non-admin user cannot add the Trusted User group"""
        self._user_group_add_non_root(self.group_trusted_user)

    def test04_debug_add_non_root(self):
        """Test that a non-admin user cannot add the Debug User group"""
        self._user_group_add_non_root(self.group_debug_user)

    def test05_trusted_remove_non_root(self):
        """Test that a non-admin user cannot remove the Trusted User group"""
        self._user_group_remove_non_root(self.group_trusted_user)

    def test06_debug_remove_non_root(self):
        """Test that a non-admin user cannot remove the Debug User group"""
        self._user_group_remove_non_root(self.group_debug_user)

    def test07_trusted_add_remove_root(self):
        """Test that the admin user can add and remove users"""
        self._group_user_add_remove_root(self.group_trusted_user)

    def test08_debug_add_remove_root(self):
        """Test that the admin user can add and remove users"""
        self._group_user_add_remove_root(self.group_debug_user)

    def test09_trusted_add_remove_non_root(self):
        """Test that a non-admin user cannot modify the Trusted User group's
        users"""
        self._group_user_add_remove_non_root(self.group_trusted_user)

    def test10_debug_add_remove_non_root(self):
        """Test that a non-admin user cannot modify the Debug User group's
        users"""
        self._group_user_add_remove_non_root(self.group_debug_user)

    def _user_group_add_remove_root(self, user_group):
        self.assertNotIn(user_group, self.user_2.groups_id)

        # Add group
        self.user_2.write({ 'groups_id': [(4, user_group.id)] })
        self.assertIn(user_group, self.user_2.groups_id)

        # Remove group
        self.user_2.write({ 'groups_id': [(3, user_group.id)] })
        self.assertNotIn(user_group, self.user_2.groups_id)

        # Add group via replacement
        self.user_2.write({ 'groups_id':
                                [(6, 0, [user_group.id])] })
        self.assertIn(user_group, self.user_2.groups_id)

        # Remove group via replacement
        self.user_2.write({ 'groups_id': [(6, 0, [])] })
        self.assertNotIn(user_group, self.user_2.groups_id)

        # Remove all groups
        self.user_2.write({ 'groups_id': [(4, user_group.id)] })
        self.assertIn(user_group, self.user_2.groups_id)
        self.user_2.write({ 'groups_id': [(5,)] })
        self.assertNotIn(user_group, self.user_2.groups_id)

    def _user_group_add_non_root(self, user_group):
        user_2 = self.user_2.sudo(self.user_1.id)
        self.assertNotIn(user_group, user_2.groups_id)

        # Add group
        with self.assertRaises(AccessError):
            user_2.write({ 'groups_id': [(4, user_group.id)] })
        self.assertNotIn(user_group, user_2.groups_id)

        # Add group via replacement
        with self.assertRaises(AccessError):
            user_2.write({ 'groups_id':
                               [(6, 0, [user_group.id])] })
        self.assertNotIn(user_group, user_2.groups_id)

    def _user_group_remove_non_root(self, user_group):
        self.user_2.write({ 'groups_id': [(4, user_group.id)] })

        user_2 = self.user_2.sudo(self.user_1.id)
        self.assertIn(user_group, user_2.groups_id)

        # Remove group
        with self.assertRaises(AccessError):
            user_2.write({ 'groups_id': [(3, user_group.id)] })
        self.assertIn(user_group, user_2.groups_id)

        # Replacement no-op
        user_2.write({ 'groups_id': [(6, 0, user_2.groups_id.ids)] })
        self.assertIn(user_group, user_2.groups_id)

        # Remove group via replacement
        with self.assertRaises(AccessError):
            user_2.write({ 'groups_id': [(6, 0, [])] })
        self.assertIn(user_group, user_2.groups_id)

        # Remove all groups
        with self.assertRaises(AccessError):
            user_2.write({ 'groups_id': [(5,)] })
        self.assertIn(user_group, user_2.groups_id)

    def _group_user_add_remove_root(self, user_group):
        self._test_group_user_add_remove(self.env.user, user_group, self.user_2)

    def _group_user_add_remove_non_root(self, user_group):
        # Check that user_1 can modify the users of a different group
        self._test_group_user_add_remove(self.user_1,
                                         self.group_access_rights, self.user_2)

        # Check that user_1 cannot modify the users of the User group
        group_user = user_group.sudo(self.user_1.id)
        for act in [(4, self.user_2.id), (3, self.user_2.id), (5,), (6, 0, [])]:
            with self.assertRaises(AccessError):
                group_user.sudo(self.user_1.id).write({ 'users': [act] })
            self.assertNotIn(self.user_2, group_user.users)

    def _test_group_user_add_remove(self, user, test_group, test_user):
        """Test that user can modify test_group's users"""
        test_group = test_group.sudo(user.id)

        self.assertNotIn(test_user, test_group.users)

        # Add user
        test_group.write({ 'users': [(4, test_user.id)] })
        self.assertIn(test_user, test_group.users)

        # Remove user
        test_group.write({ 'users': [(3, test_user.id)] })
        self.assertNotIn(test_user, test_group.users)
