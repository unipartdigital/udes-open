from odoo.tests import common
from odoo.tools import mute_logger, config
from odoo import http


class DesktopAccessBase(common.HttpSavepointCase):
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
                "groups_id": [(6, 0, [cls.group_desktop_access.id, cls.group_internal_user.id])],
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


class TestDesktopAccess(DesktopAccessBase):
    """
    Check that when the desktop access group is not present on a user
    the user gets redirected to a `No Access` page instead of UDES.
    Also check backend access is unaffected by this group
    """

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


class TestURLAccess(DesktopAccessBase):
    """
    Ensure load() hook is working as intended by blocking access when users
    visit actions directly via URL which they would otherwise not see via menuitems
    """

    @classmethod
    def setUpClass(cls):
        """
        Have 2 users, one with Administration/Access Rights, one without,
        but both with desktop access
        """
        super().setUpClass()

        cls.group_erp_manager = cls.env.ref("base.group_erp_manager")
        cls.group_trusted_user = cls.env.ref("udes_security.group_trusted_user")
        # Make both users have desktop access
        cls.user_2.write({"groups_id": [(4, cls.group_desktop_access.id)]})
        # But grant only user_1 technical features and trusted user
        cls.user_1.write({"groups_id": [(4, cls.group_erp_manager.id)]})
        cls.user_1.write({"groups_id": [(4, cls.group_trusted_user.id)]})

    def url_open_json(
        self, url, data=None, files=None, timeout=10, headers=None, allow_redirects=True
    ):
        """
        Copy of url_open() in odoo/odoo/tests/common.py,
        changed to pass data to the json kwarg in self.opener.post()
        to allow posting to json endpoints"""
        self.env["base"].flush()
        if url.startswith("/"):
            url = "http://%s:%s%s" % ("127.0.0.1", config["http_port"], url)
        if data or files:
            return self.opener.post(
                url,
                json=data,
                files=files,
                timeout=timeout,
                headers=headers,
                allow_redirects=allow_redirects,
            )
        return self.opener.get(
            url, timeout=timeout, headers=headers, allow_redirects=allow_redirects
        )

    def load_action(self, action_id):
        """
        Helper function to simulate loading an action via URL

        :param: action_id: int() for an action (ir.actions.server, ir.actions.act_window, etc..)

        :return: requests.models.Response() object
        """
        return self.url_open_json(
            url=f"{self.base_url}/web/action/load",
            data={"params": {"action_id": action_id}},
        )

    def test_access_to_actions(self):
        """
        Load various actions as both user_1 and user_2
        and ensure errors are raised accordingly
        """
        # Settings/Technical/Sequences & Identifiers/Sequences (ir.actions.act_window)
        sequence_action = self.env.ref("base.ir_sequence_form")
        # Settings/Users & Companies/Users (ir.actions.act_window)
        users_action = self.env.ref("base.action_res_users")
        # Discuss (ir.actions.client)
        discuss_action = self.env.ref("mail.action_discuss")
        # Apps/Apps/Third-Party Apps (ir.actions.act_url)
        third_party_apps_action = self.env.ref("base.menu_third_party")
        # DEBT: There are no ir.actions.server, or ir.actions.report actions available,
        # in future add them to setUpClass
        user_action_access_list = [
            {
                "user": self.user_1,
                "action": sequence_action,
                "has_access": True,
            },
            {
                "user": self.user_2,
                "action": sequence_action,
                "has_access": False,
            },
            {
                "user": self.user_1,
                "action": users_action,
                "has_access": True,
            },
            {
                "user": self.user_2,
                "action": users_action,
                "has_access": False,
            },
            {
                "user": self.user_1,
                "action": discuss_action,
                "has_access": True,
            },
            {
                "user": self.user_2,
                "action": discuss_action,
                "has_access": True,
            },
            {
                "user": self.user_1,
                "action": third_party_apps_action,
                "has_access": True,
            },
            {
                "user": self.user_2,
                "action": third_party_apps_action,
                "has_access": True,
            },
        ]
        access_error_text = "odoo.exceptions.AccessError"
        for user_action_access_dict in user_action_access_list:
            user_login = user_action_access_dict["user"].login
            action_id = user_action_access_dict["action"].id
            has_access = user_action_access_dict["has_access"]
            with self.subTest(
                msg=f"Trying action: {action_id} as user: {user_login}, has access: {has_access}"
            ):
                self.authenticate(user_login, "password")
                if has_access:
                    response = self.load_action(action_id)
                    self.assertNotIn(access_error_text, response.text)
                else:
                    # Only surpress warnings if we expect them, it does lead to some duplicated code though
                    with mute_logger("odoo.addons.udes_security.controllers.main", "odoo.http"):
                        response = self.load_action(action_id)
                    self.assertIn(access_error_text, response.text)
