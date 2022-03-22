from odoo import http
from odoo.http import request, route, Controller
from .web import Home


class CustomerPortal(Controller):
    @route(["/no_desktop_access"], type="http", auth="user", website=True)
    def no_desktop_access(self, **kw):
        """
        Landing page for users that do not have direct access to the UDES desktop.

        Users that do have access are redirected.
        """
        if Home().user_has_desktop_access():
            return http.local_redirect("/web")

        return request.render("udes_security.no_desktop_access")
