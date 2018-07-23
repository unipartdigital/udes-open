# -*- coding: utf-8 -*-

from odoo.http import request
from odoo import http, exceptions
import odoo.addons.web.controllers.main as main
import odoo.addons.auth_signup.controllers.main as authmain
from odoo.addons.web.controllers.main import ensure_db
from ..common import remove_external_redirect


class AuthSignupHome(authmain.AuthSignupHome):

    # Override web_login function
    @http.route()
    def web_login(self, *args, **kw):

        ensure_db()

        # Validate redirect that is passed to (grand) parent
        redirect = kw.get('redirect', None)
        redirect = remove_external_redirect(redirect)
        response = main.Home.web_login(self, redirect)
        response.qcontext.update(self.get_auth_signup_config())

        # Validate redirect used here
        redirect = request.params.get('redirect')
        redirect = remove_external_redirect(redirect)

        if request.httprequest.method == 'GET' and request.session.uid and redirect:
            # Redirect if already logged in and redirect param is present
            return http.redirect_with_hash(redirect)
        return response
