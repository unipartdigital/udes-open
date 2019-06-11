"""Open redirect filter"""

import logging
from werkzeug import urls
from werkzeug.exceptions import BadRequest
from odoo import http
from odoo.tools.translate import _
from odoo.addons.web.controllers import main

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
        redirect = kwargs.get('redirect')
        if redirect is not None and self.is_absolute_url(redirect):
            _logger.error("Invalid redirection attempted: %s", redirect)
            raise BadRequest(_("Invalid redirection attempted"))
        return self.func(*args, **kwargs)

    @staticmethod
    def is_absolute_url(url):
        """Test if a URL is an absolute URL"""
        return True if bool(urls.url_parse(url).scheme) or bool(urls.url_parse(url).netloc) else False


class Home(main.Home):
    """Web client controller"""

    @http.route()
    @no_absolute_redirect
    def web_client(self, *args, **kwargs):
        """Prevent absolute redirects on /web"""
        return super().web_client(*args, **kwargs)

    @http.route()
    @no_absolute_redirect
    def web_login(self, *args, **kwargs):
        """Prevent absolute redirects on /web/login"""
        return super().web_login(*args, **kwargs)
