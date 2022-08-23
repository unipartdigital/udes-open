import logging
from odoo import http, _
from odoo.addons.web.controllers import main
from odoo.http import request
from werkzeug import urls
from werkzeug.urls import url_unquote
from werkzeug.exceptions import BadRequest
from fnmatch import fnmatch

_logger = logging.getLogger(__name__)


class no_absolute_redirect(object):
    """Decorator to mark a route as forbidding absolute redirects

    If the decorated route is called with a "redirect" query parameter
    containing an absolute URL, the request will be terminated with an
    exception.
    """

    def __init__(self, func):
        self.func = func

    @property
    def __name__(self):
        """Copy original method name

        This is required since the method name will be introspected as
        part of calculating the controller inheritance structure.
        """
        return self.func.__name__

    def __call__(self, *args, **kwargs):
        """Call method"""
        redirect = kwargs.get("redirect")

        if redirect:
            redirect = url_unquote(redirect)
            if redirect.startswith("//"):
                # remove leading /'s which can trick the url parser but is handled by browsers
                kwargs["redirect"] = "/" + redirect.lstrip("/")
            else:
                parsed_url = urls.url_parse(redirect)

                if self.is_absolute_url(parsed_url) and not self.domain_is_allowlisted(parsed_url):
                    _logger.error("Invalid redirection attempted: %s", redirect)
                    raise BadRequest(_("Invalid redirection attempted"))

        return self.func(*args, **kwargs)

    @staticmethod
    def is_absolute_url(parsed_url):
        """Returns True if URL is an absolute URL, else False"""
        return True if bool(parsed_url.scheme) or bool(parsed_url.netloc) else False

    @classmethod
    def domain_is_allowlisted(cls, parsed_url):
        """Returns True if a URL domain is listed in the allowlist"""
        DomainAllowlist = http.request.env["udes_security.domain.allowlist"]
        query_domain = parsed_url.host

        if DomainAllowlist.search([("domain", "=", parsed_url.host)]):
            return True
        else:
            for allow_domain in DomainAllowlist.search([]):
                if fnmatch(query_domain, allow_domain.domain):
                    return True
        return False


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
    @no_absolute_redirect
    def web_client(self, *args, **kwargs):
        """
        Override API to check debug privileges. Mostly, ensure right users can activate debug.
        """
        self._check_debug_access_privileges(request)
        return super().web_client(*args, **kwargs)

    @http.route()
    @no_absolute_redirect
    def web_login(self, *args, **kwargs):
        """
        Override API to check debug privileges. In the login case, we also do not want to show
        the login as superuser button.
        """
        self._check_debug_access_privileges(request)
        return super().web_login(*args, **kwargs)
