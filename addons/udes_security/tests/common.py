"""Common code for password configuration and testing."""

from odoo.exceptions import UserError


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
