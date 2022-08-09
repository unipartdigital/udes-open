from odoo.tests import common
from odoo.tools import mute_logger
from werkzeug.urls import url_join


class TestRedirect(common.HttpCase):
    """Tests for password complexity"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")

    def _get_url(self, url):
        return url_join(self.base_url, url)

    def assertFailedRedirect(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertIn("Bad Request", response.text)
        self.assertIn("Invalid redirection attempted", response.text)

    def assertNotFound(self, response, redirect_url):
        """ODOO internal redirection to page not found"""
        self.assertEqual(response.status_code, 404)
        self.assertIn("We couldn't find the page you're looking for!", response.text)
        # Look for redirect
        for resp in response.history:
            if (
                resp.status_code == 303
                and resp.headers["Location"].replace("127.0.0.1", "localhost")
                == redirect_url
            ):
                break
        else:
            raise AssertionError("Redirect not found")

    def assertSuccessfulRedirect(self, response, redirect_url):
        self.assertEqual(response.status_code, 200)
        # Look for redirect
        for resp in response.history:
            if (
                resp.status_code == 303
                and resp.headers["Location"].replace("127.0.0.1", "localhost")
                == redirect_url
            ):
                break
        else:
            raise AssertionError("Redirect not found")

    @mute_logger("odoo.addons.udes_security.controllers.redirect")
    def test_absolute_throws_bad_request(self):
        self.assertFailedRedirect(self.url_open("/web?redirect=http://baddomain.com"))

    def test_local_does_not_throw_bad_request(self):
        self.assertSuccessfulRedirect(
            self.url_open("/web?redirect=/web/login"),
            redirect_url=self._get_url("/web/login"),
        )

    def test_double_forward_slash_redirects_locally(self):
        self.authenticate("admin", "admin")
        self.assertNotFound(
            self.url_open("/web?redirect=//baddomain.com"),
            redirect_url=self._get_url("/baddomain.com"),
        )

    def test_quad_forward_slash_redirects_locally(self):
        self.authenticate("admin", "admin")
        self.assertNotFound(
            self.url_open("/web?redirect=////baddomain.com"),
            redirect_url=self._get_url("/baddomain.com"),
        )

    def test_url_encoded_double_forward_slash_redirects_locally(self):
        self.authenticate("admin", "admin")
        self.assertNotFound(
            self.url_open("/web?redirect=%2F%2Fbaddomain.com"),
            redirect_url=self._get_url("/baddomain.com"),
        )

    def test_allow_listed_domain_redirects(self):
        DomainAllowlist = self.env["udes_security.domain.allowlist"]

        self.authenticate("admin", "admin")

        self.assertFailedRedirect(self.url_open("/web?redirect=http://google.com"))

        DomainAllowlist.create({"name": "Google", "domain": "google.com"})
        self.assertSuccessfulRedirect(
            self.url_open("/web?redirect=http://google.com"),
            redirect_url="http://google.com",
        )

    def test_allow_listed_wildcarded_domain_redirects(self):
        DomainAllowlist = self.env["udes_security.domain.allowlist"]

        self.authenticate("admin", "admin")

        allowed_domain = DomainAllowlist.create(
            {"name": "Google", "domain": "google.com"}
        )
        self.assertFailedRedirect(
            self.url_open("/web?redirect=https://support.google.com/")
        )

        allowed_domain.domain = "*.google.com"
        self.assertSuccessfulRedirect(
            self.url_open("/web?redirect=https://support.google.com/"),
            redirect_url="https://support.google.com/",
        )
