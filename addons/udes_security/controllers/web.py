from odoo import http
from odoo.addons.web.controllers.main import Home
from odoo.http import request


class Home(Home):
    def user_has_desktop_access(self):
        """
        Return True if session user has desktop access group and internal user group,
        otherwise False
        """
        User = request.env["res.users"].sudo()

        user = User.browse(request.session.uid)
        has_desktop_access = user.has_group("base.group_user") and user.has_group(
            "udes_security.group_desktop_access"
        )
        return has_desktop_access

    @http.route("/", type="http", auth="none")
    def index(self, *args, **kw):
        """Extend controller to redirect non-desktop user if they try to access the main system"""
        if request.session.uid and not self.user_has_desktop_access():
            return http.local_redirect("/no_desktop_access", query=request.params, keep_hash=True)
        return super(Home, self).index(*args, **kw)

    @http.route("/web", type="http", auth="none")
    def web_client(self, s_action=None, **kw):
        """Extend controller to redirect non-desktop user if they try to access the main system"""
        if request.session.uid and not self.user_has_desktop_access():
            return http.local_redirect("/no_desktop_access", query=request.params, keep_hash=True)
        return super(Home, self).web_client(s_action, **kw)

    def _login_redirect(self, uid, redirect=None):
        """Extend controller to redirect user after they've logged in if they don't have desktop access"""
        if request.session.uid and not redirect and not self.user_has_desktop_access():
            redirect = "/no_desktop_access"
        return super(Home, self)._login_redirect(uid, redirect=redirect)
