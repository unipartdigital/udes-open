# -*- coding: utf-8 -*-

from odoo.http import request
from odoo import http, exceptions
from odoo.exceptions import AccessError, UserError
import odoo.addons.web.controllers.main as main
from odoo.addons.web.controllers.main import ensure_db
import werkzeug
from ..common import remove_external_redirect


class Home(main.Home):

    # Intercept and replace redirect param
    def _login_redirect(self, uid, redirect=None):
        redirect = remove_external_redirect(redirect)
        res = super(Home, self)._login_redirect(uid, redirect)
        return res

    # Override web_client function
    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        ensure_db()
        if not request.session.uid:
            return werkzeug.utils.redirect('/web/login', 303)
        # Begin UDES security modifications
        redirect = kw.get('redirect')
        redirect = remove_external_redirect(redirect)
        if redirect:
            return werkzeug.utils.redirect(redirect, 303)
        # End UDES security modifications
        request.uid = request.session.uid
        try:
            context = request.env['ir.http'].webclient_rendering_context()
            response = request.render('web.webclient_bootstrap', qcontext=context)
            response.headers['X-Frame-Options'] = 'DENY'
            return response
        except AccessError:
            return werkzeug.utils.redirect('/web/login?error=access')
