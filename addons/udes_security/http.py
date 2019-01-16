import werkzeug.contrib.sessions

import odoo.http
from odoo.http import request
from odoo.http import OpenERPSession
from odoo.http import Root
from odoo.http import dispatch_rpc
from odoo.service import security

root = Root()


def authenticate(self, db, login=None, password=None, uid=None):
    """
    Authenticate the current user with the given db, login and
    password. If successful, store the authentication parameters in the
    current session and request.

    :param uid: If not None, that user id will be used instead the login
                to authenticate the user.
    """

    if uid is None:
        wsgienv = request.httprequest.environ
        env = dict(
            base_location=request.httprequest.url_root.rstrip('/'),
            HTTP_HOST=wsgienv['HTTP_HOST'],
            REMOTE_ADDR=wsgienv['REMOTE_ADDR'],
        )
        uid = dispatch_rpc('common', 'authenticate',
                           [db, login, password, env])
    else:
        security.check(db, uid, password)

    if uid:
        request.httprequest.session = root.session_store.new()
        self = request.httprequest.session

    self.db = db
    self.uid = uid
    self.login = login
    self.session_token = uid and security.compute_session_token(self,
                                                                request.env)
    request.uid = uid
    request.disable_db = False

    if uid: self.get_context()
    return uid


odoo.http.OpenERPSession.authenticate = authenticate
