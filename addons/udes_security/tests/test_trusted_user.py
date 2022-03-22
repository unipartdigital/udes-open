from odoo.exceptions import AccessError
from odoo.tests import common


class TestTrustedUser(common.SavepointCase):
    """
    Check that only the admin user can add and remove the Trusted User group
    """

    @classmethod
    def setUpClass(cls):
        """
        Create two users for testing
        """
        super().setUpClass()

        User = cls.env["res.users"]

        cls.group_access_rights = cls.env.ref("base.group_system")
        cls.group_internal_user = cls.env.ref("base.group_user")
        cls.group_trusted_user = cls.env.ref("udes_security.group_trusted_user")

        cls.user_1 = User.create(
            {
                "name": "Test User 1",
                "login": "test_user_1",
                "groups_id": [(6, 0, [cls.group_access_rights.id, cls.group_internal_user.id])],
            }
        )
        cls.user_2 = User.create({"name": "Test User 2", "login": "test_user_2"})

    def test01_user_group_add_remove_root(self):
        """Test that the root user can add and remove the Trusted User group"""
        self.assertNotIn(self.group_trusted_user, self.user_2.groups_id)

        # Add group
        self.user_2.groups_id = [(4, self.group_trusted_user.id)]
        self.assertIn(self.group_trusted_user, self.user_2.groups_id)

        # Remove group
        self.user_2.groups_id = [(3, self.group_trusted_user.id)]
        self.assertNotIn(self.group_trusted_user, self.user_2.groups_id)

        # Add group via replacement
        self.user_2.groups_id = [(6, 0, [self.group_trusted_user.id])]
        self.assertIn(self.group_trusted_user, self.user_2.groups_id)

        # Remove group via replacement
        self.user_2.groups_id = [(6, 0, [])]
        self.assertNotIn(self.group_trusted_user, self.user_2.groups_id)

        # Remove all groups
        self.user_2.groups_id = [(4, self.group_trusted_user.id)]
        self.assertIn(self.group_trusted_user, self.user_2.groups_id)
        self.user_2.groups_id = [(5,)]
        self.assertNotIn(self.group_trusted_user, self.user_2.groups_id)

    def test02_user_group_add_non_root(self):
        """Test that a non-root user cannot add the Trusted User group"""
        user_2 = self.user_2.with_user(self.user_1)
        self.assertNotIn(self.group_trusted_user, user_2.groups_id)

        # Add group
        with self.assertRaises(AccessError):
            user_2.groups_id = [(4, self.group_trusted_user.id)]
        self.assertNotIn(self.group_trusted_user, user_2.groups_id)

        # Add group via replacement
        with self.assertRaises(AccessError):
            user_2.groups_id = [(6, 0, [self.group_trusted_user.id])]
        self.assertNotIn(self.group_trusted_user, user_2.groups_id)

    def test03_user_group_remove_non_root(self):
        """Test that a non-root user cannot remove the Trusted User group"""
        self.user_2.groups_id = [(4, self.group_trusted_user.id)]
        user_2 = self.user_2.with_user(self.user_1)
        self.assertIn(self.group_trusted_user, user_2.groups_id)

        # Remove group
        with self.assertRaises(AccessError):
            user_2.groups_id = [(3, self.group_trusted_user.id)]
        self.assertIn(self.group_trusted_user, user_2.groups_id)

        # Replacement no-op
        user_2.groups_id = [(6, 0, user_2.groups_id.ids)]
        self.assertIn(self.group_trusted_user, user_2.groups_id)

        # Remove group via replacement
        with self.assertRaises(AccessError):
            user_2.groups_id = [(6, 0, [])]
        self.assertIn(self.group_trusted_user, user_2.groups_id)

        # Remove all groups
        with self.assertRaises(AccessError):
            user_2.groups_id = [(5,)]
        self.assertIn(self.group_trusted_user, user_2.groups_id)

    def test04_group_user_add_remove_root(self):
        """Test that the root user can add and remove users"""
        self._test_group_user_add_remove(
            self.env.user, self.group_trusted_user, self.user_2
        )

    def test05_group_user_add_remove_non_root(self):
        """Test that a non-root user cannot modify the Trusted User group's
        users"""
        # Check that user_1 can modify the users of a different group
        self._test_group_user_add_remove(
            self.user_1, self.group_access_rights, self.user_2
        )

        # Check that user_1 cannot modify the users of the Trusted User group

        group_trusted_user = self.group_trusted_user.with_user(self.user_1)
        for act in [(4, self.user_2.id), (3, self.user_2.id), (5,), (6, 0, [])]:
            with self.assertRaises(AccessError):
                group_trusted_user.with_user(self.user_1).write({"users": [act]})
            self.assertNotIn(self.user_2, group_trusted_user.users)

    def _test_group_user_add_remove(self, user, test_group, test_user):
        """Test that user can modify test_group's users"""
        test_group = test_group.with_user(user)
        self.assertNotIn(test_user, test_group.users)

        # Add user made change from 4 to 3 for testing
        test_group.users = [(4, test_user.id)] 
        self.assertIn(test_user, test_group.users)

        # Remove user
        test_group.users = [(3, test_user.id)]
        self.assertNotIn(test_user, test_group.users)
