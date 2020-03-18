from odoo.tests import common
from odoo.service import security
import uuid
import requests
from odoo.http import root


_store = root.session_store


class TestSingleSession(common.HttpCase):
    """
    Check that a user with u_restrict_to_single_session has previous sessions cleared on login
    """

    def setUp(self):
        super(TestSingleSession, self).setUp()
        self.good_password = (
            "SuitablyComplexPassword951@"
        )  # To prevent issues with password complexity rules
        with self.cursor() as cr:
            env = self.env(cr)
            self.user_1 = env["res.users"].create({"name": "Test User 1", "login": "test_user_1"})
            self.user_1.password = self.good_password

        IrConfig = self.env["ir.config_parameter"].sudo()
        self.base_url = IrConfig.get_param("web.base.url")

    def restrict_multiple_sessions(self, restrict):
        with self.cursor() as cr:
            env = self.env(cr)
            env["res.users"].browse(self.user_1.id).u_restrict_to_single_session = restrict

    def assertSessionValid(self, sids):
        store_list = _store.list()
        for sid in sids:
            self.assertTrue((sid in store_list))
            self.assertTrue(security.check_session(_store.get(sid), self.env))

    def assertSessionInvalid(self, sids):
        store_list = _store.list()
        for sid in sids:
            self.assertFalse((sid in store_list))
            self.assertFalse(_store.get(sid)['uid'])

    def jsonrpc(self, url, method="call", params=None):
        """ Make a jsonrpc call """
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": uuid.uuid4().hex}
        req = requests.post(self.base_url + url, json=payload)
        return req.json()

    def login(self):
        """ login and return session id """
        db = self.env.cr.dbname
        login = self.user_1.login
        password = self.good_password
        return self.jsonrpc(
            "/web/session/authenticate", params={"login": login, "password": password, "db": db}
        )["result"]["session_id"]

    def test01_user_can_have_multiple_active_sessions(self):
        """Test that a user can have multiple active sessions"""
        self.restrict_multiple_sessions(False)

        # Login and get session id
        sid = self.login()

        # Login and get session id
        sid2 = self.login()

        # Should have 2 different session IDs
        self.assertNotEqual(sid, sid2)

        # Check both session IDs exist in store and are valid
        self.assertSessionValid((sid, sid2))

    def test02_user_restricted_to_single_session(self):
        """Test that user is restricted to a single session"""
        self.restrict_multiple_sessions(True)

        sids = []
        # Login 4x and get check each is valid
        for x in range(4):
            sid = self.login()
            # Check session is valid
            self.assertSessionValid((sid,))
            self.assertSessionInvalid(sids)
            sids.append(sid)
