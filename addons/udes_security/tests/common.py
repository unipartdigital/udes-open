"""Common code for password configuration and testing."""

from odoo.exceptions import UserError
import werkzeug

class PasswordMixin:
    """Methods for testing and configuring passwords."""

    def assertPasswordsInvalid(self, password_list):
        """Set each password, assert that error is raised."""
        for password in password_list:
            with self.subTest(password=password):
                with self.assertRaises(
                    UserError, msg='Password "%s" did not raise an error as expected' % password
                ):
                    self.user1.password = password

    def set_passwords(self, passwords):
        """Set each password in the provided collection."""
        for password in passwords:
            with self.subTest(password=password):
                self.user1.password = password

    @classmethod
    def set_complexity(cls, length=None, numeric=None, upper=None, lower=None, special=None):
        """Set the complexity on test company as per input."""
        vals = {
            attr: value
            for attr, value in {
                "u_minimum_password_length": length,
                "u_minimum_password_lower": lower,
                "u_minimum_password_upper": upper,
                "u_minimum_password_numeric": numeric,
                "u_minimum_password_special": special,
            }.items()
            if value is not None
        }
        cls.company.write(vals)


class RedirectMixin:
    """Methods for testing redirects"""

    def _get_url(self, url):
        # With these versions and higher, response history headers "Location"
        # key does not contain the base url.
        # Still support people on older versions of python & werkzeug.
        if werkzeug.__version__ == "2.3.7":
            return url
        else:
            return werkzeug.urls.url_join(self.base_url, url)

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
                and resp.headers["Location"] == redirect_url
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
                and resp.headers["Location"] == redirect_url
            ):
                break
        else:
            raise AssertionError("Redirect not found")
