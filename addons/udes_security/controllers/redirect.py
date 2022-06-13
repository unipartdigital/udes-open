import logging
from odoo import http
from odoo.addons.web.controllers import main
from odoo.http import request

_logger = logging.getLogger(__name__)


class Home(main.Home):
    """Web client controller"""

    @staticmethod
    def _disable_debug(request):
        """
        Disable debug by removing debug key from request parameters and resetting debug key in session
        """
        # Always disable debug
        request.session.debug = ""
        # Remove parameter which also avoids showing superuser button on login or other places
        if "debug" in request.params:
            request.params.pop("debug")

    def _check_debug_access_privileges(self, request):
        """
        Ensure that only Superuser (including admin) or users who belong to trusted user group
        have access to debug mode. If not, debug mode is disabled by overriding request parameters.
        Also, disable debug if there is no session.
        """
        user = request.env.user.browse(request.session.uid)

        if not request.session.uid or not user._is_superuser_or_admin() and not user.u_is_trusted_user:
            self._disable_debug(request)

    @http.route()
    def web_client(self, *args, **kwargs):
        """
        Override API to check debug privileges. Mostly, ensure right users can activate debug.
        """
        self._check_debug_access_privileges(request)
        return super().web_client(*args, **kwargs)

    @http.route()
    def web_login(self, *args, **kwargs):
        """
        Override API to check debug privileges. In the login case, we also do not want to show
        the login as superuser button.
        """
        self._check_debug_access_privileges(request)
        return super().web_login(*args, **kwargs)
