from .common import UDESHttpCase

from odoo.tests import common
from odoo.tools import mute_logger, config


class DesktopAccessBase(UDESHttpCase):
    def setUp(self):
        """
        Create two users for testing and set their passwords so logging in
        from controllers can be simulated
        """
        super().setUp()

        User = self.env["res.users"]
        self.password = "abcdefgHIJKLMNOP12345("

        self.group_internal_user = self.env.ref("base.group_user")
        self.user_1 = User.create(
            {
                "name": "Test User 1",
                "login": "test_user_1",
                "groups_id": [(6, 0, [self.group_internal_user.id])],
            }
        )
        self.user_2 = User.create(
            {
                "name": "Test User 2",
                "login": "test_user_2",
                "groups_id": [(6, 0, [self.group_internal_user.id])],
            }
        )
        self.base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        self.user_1.password = self.password
        self.user_2.password = self.password


@common.at_install(False)
@common.post_install(True)
class TestURLAccess(DesktopAccessBase):
    """
    Ensure load() hook is working as intended by blocking access when users
    visit actions directly via URL which they would otherwise not see via menuitems
    """

    def setUp(self):
        """
        Have 2 users, one with Administration/Access Rights, one without
        """
        super().setUp()

        self.group_erp_manager = self.env.ref("base.group_erp_manager")
        # Grant only user_1 technical features
        self.user_1.write({"groups_id": [(4, self.group_erp_manager.id)]})

    def url_open_json(self, url, data=None, timeout=10):
        """
        Copy of url_open() in odoo/odoo/tests/common.py,
        changed to pass data to the json kwarg in self.opener.post()
        to allow posting to json endpoints
        """
        if url.startswith("/"):
            url = "http://%s:%s%s" % ("127.0.0.1", config["http_port"], url)
        if data:
            return self.opener.post(url, json=data, timeout=timeout)
        return self.opener.get(url, timeout=timeout)

    def load_action(self, action_id):
        """
        Helper function to simulate loading an action via URL

        :param: action_id: int() for an action (ir.actions.server, ir.actions.act_window, etc..)

        :return: requests.models.Response() object
        """
        with self.release():
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
        # Apps/App Store (ir.actions.client)
        app_store_action = self.env.ref("base.module_mi")
        # DEBT: There are no ir.actions.server, ir.actions.report, or ir.actions.act_url
        # actions available, in future add them to setUpClass
        user_action_access_list = [
            {
                "user": self.user_1,
                "action": sequence_action,
                "has_access": False,
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
                "action": app_store_action,
                "has_access": False,
            },
            {
                "user": self.user_2,
                "action": app_store_action,
                "has_access": False,
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
                self.authenticate(user_login, self.password)
                if has_access:
                    response = self.load_action(action_id)
                    self.assertNotIn(access_error_text, response.text)
                else:
                    # Only surpress warnings if we expect them, it does lead to some duplicated code though
                    with mute_logger("odoo.addons.udes_security.controllers.main", "odoo.http"):
                        response = self.load_action(action_id)
                    self.assertIn(access_error_text, response.text)
