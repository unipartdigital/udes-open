from odoo.tests import common
from odoo import http


class TestDesktopAccess(common.HttpSavepointCase):
    """
    Check that when the desktop access group is not present on a user
    the user gets redirected to a `No Access` page instead of UDES.
    Also check backend access is unaffected by this group
    """

    @classmethod
    def setUpClass(cls):
        """
        Create two users for testing and set their passwords so logging in
        from controllers can be simulated
        """
        super().setUpClass()

        User = cls.env["res.users"]

        cls.group_internal_user = cls.env.ref("base.group_user")
        cls.group_desktop_access = cls.env.ref("udes_security.group_desktop_access")
        cls.user_1 = User.create(
            {
                "name": "Test User 1",
                "login": "test_user_1",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.group_desktop_access.id,
                            cls.group_internal_user.id,
                        ],
                    )
                ],
            }
        )
        cls.user_2 = User.create(
            {
                "name": "Test User 2",
                "login": "test_user_2",
                "groups_id": [(6, 0, [cls.group_internal_user.id])],
            }
        )
        cls.base_url = cls.env["ir.config_parameter"].sudo().get_param("web.base.url")
        cls.set_passwords(cls.user_1 | cls.user_2, "password")

    @classmethod
    def set_passwords(cls, users, password):
        """
        Helper function to batch set passwords for users.
        There may be a better way to achieve this without using wizards,
        which I don't know about
        :param: users: res.users(x,) recordset(s)
        :param: password: str() what to set the password to
        """
        ChangePasswordWizard = cls.env["change.password.wizard"]
        ChangePasswordUser = cls.env["change.password.user"]
        wizard = ChangePasswordWizard.create({})
        for user in users:
            line_vals = {
                "wizard_id": wizard.id,
                "user_id": user.id,
                "user_login": user.login,
                "new_passwd": password,
            }
            ChangePasswordUser.create(line_vals)
        wizard.change_password_button()

    def log_in_as(self, user, password):
        """Helper function to reset auth, then hit the /web/login controller
        as a particular user and return the result"""
        self.authenticate(None, None)  # Reset & make it possible to get a csrf token
        return self.url_open(
            url=f"{self.base_url}/web/login",
            data={
                "login": user.login,
                "password": password,
                "csrf_token": http.WebRequest.csrf_token(self),
            },
        )

    def test_user_with_group_can_access_desktop(self):
        """Ensure that users with the group can log in via the desktop and
        get redirected to /web as normal"""
        result = self.log_in_as(self.user_1, "password")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.url, f"{self.base_url}/web")
        self.assertNotIn("Access Denied", result.text)

    def test_user_without_group_cannot_access_desktop(self):
        """Ensure that users without the group can not log in via the desktop
        and get redirected to /no_desktop_access"""
        result = self.log_in_as(self.user_2, "password")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.url, f"{self.base_url}/no_desktop_access")
        self.assertIn("Access Denied", result.text)

    def test_all_users_can_access_database(self):
        """Ensure that restricted desktop access does not affect backend/database access"""
        ResPartner = self.env["res.partner"]
        # Use a base model these users can access which has recordsets in it
        self.assertTrue(ResPartner.with_user(self.user_1).search([]).read(["name"]))
        self.assertTrue(ResPartner.with_user(self.user_2).search([]).read(["name"]))
