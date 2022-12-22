"""Unit tests for password complexity settings."""

from odoo.tests.common import SavepointCase
from . import common


class TestPasswordComplexity(SavepointCase, common.PasswordMixin):
    """Tests for password complexity."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()
        cls.User = cls.env["res.users"]
        cls.company = cls.env["res.company"].create({"name": "Unipart"})
        cls.user1 = cls.User.create(
            {
                "name": "Agnesz",
                "login": "agnesz",
                "company_ids": cls.company,
                "company_id": cls.company.id,
            }
        )

    def test01_password_length(self):
        """Test password has sufficient length."""
        self.set_complexity(length=13, numeric=0, upper=0, lower=0, special=0)

        invalid = (
            "A",
            "Tr0ub4dor&3",
            "!!!!!!!!!!!!",
            "Password",
            "Password123!",
            "admin",
        )
        self.assertPasswordsInvalid(invalid)

        valid = (
            "correcthorsebatterystaple",
            "abcdefghijklmopqrstuvwxyz",
            "12345678901234567890",
            "!!!!!!!!!!!!!" "Password123!___",
        )
        self.set_passwords(valid)

    def test02_password_numeric(self):
        """Test password has sufficient numeric characters."""
        self.set_complexity(length=0, numeric=4, upper=0, lower=0, special=0)

        invalid = (
            "A",
            "Tr0ub4dor&3",
            "!!!!!!!!!!!!",
            "Password",
            "Password123!",
            "admin",
            "1abcd2efghij3",
        )
        self.assertPasswordsInvalid(invalid)

        valid = (
            "1correct2horse3battery4staple",
            "1234abc",
            "abc1234",
            "0000",
            "Password1234!___",
            "Test1Split2Numerics3In4Password",
        )
        self.set_passwords(valid)

    def test03_password_upper(self):
        """Test password has sufficient uppercase characters."""
        self.set_complexity(length=0, numeric=0, upper=1, lower=0, special=0)

        invalid = (
            "a",
            "!!!!!!!!!!!!",
            "password",
            "password123!",
            "admin",
            "1abcd2efghij3",
        )
        self.assertPasswordsInvalid(invalid)

        valid = (
            "Correcthorsebatterystaple",
            "1234ABC",
            "Tr0ub4dor&3",
            "1234Abc1234",
            "A0B0C0D0E",
            "Password1234!___",
        )
        self.set_passwords(valid)

    def test04_password_lower(self):
        """Test password has sufficient lowercase characters."""
        self.set_complexity(length=0, numeric=0, upper=0, lower=3, special=0)

        invalid = (
            "A",
            "!!!!!!!!!!!!",
            "PASSWORD",
            "PASSWORD123!",
            "ADMIN",
            "A1!B2@C3£D4$E5%F6^G7&",
        )
        self.assertPasswordsInvalid(invalid)

        valid = (
            "xyz",
            "Correcthorsebatterystaple",
            "1234abc",
            "Tr0ub4dor&3",
            "1234abc1234",
            "aA0bB0cC0dD0e",
            "password1234!___",
        )
        self.set_passwords(valid)

    def test05_password_special(self):
        """Test password has sufficient special characters
        Note: _ is deliberately tested as it's treated differently in regex.
        """
        self.set_complexity(length=0, numeric=0, upper=0, lower=0, special=5)

        invalid = (
            "A",
            "!!!!",
            "!A_B@C£D",
            "@@PASSWORD123!!",
            "ADMIN",
            "A1aB2bC3cD4dE5eF6fG7g",
        )
        self.assertPasswordsInvalid(invalid)

        valid = (
            "_____",
            "_!@£$",
            "A!B@C£D$F%",
            "Tr0ub4dor&3!@£$",
            "1234;.,/]1234",
            "a!A@0£b$B%0^c&C*0(d)D_0+e",
            'password1234\'"""""',
            "p@$$w@*d",
        )
        self.set_passwords(valid)

    def test06_password_mixture(self):
        """Test a usual setup for random passwords."""
        self.set_complexity(length=14, numeric=1, upper=1, lower=1, special=1)

        invalid = (
            "A",
            "ACBDEabcde!!!!",
            "Tr0ub4dor&3",
            "!A_B@C£D",
            "@@PASSWORD123!!",
            "ADMIN",
            "A1aB2bC3cD4dE5eF6fG7g",
            "1234;.,/]1234",
        )
        self.assertPasswordsInvalid(invalid)

        valid = (
            "Sixteenchars12@_",
            "thisis4reallybadPassword!",
            "C0rrecthorsebatteryst@ple",
            "a!A@0£b$B%0^c&C*0(d)D_0+e",
            'Password1234\'"""""',
        )
        self.set_passwords(valid)

    def test07_no_raise(self):
        """Test raise_on_failure flag on _check_password_complexity method."""
        self.set_complexity(length=14, numeric=1, upper=1, lower=1, special=1)

        invalid = (
            "A",
            "ACBDEabcde!!!!",
            "Tr0ub4dor&3",
            "!A_B@C£D",
            "@@PASSWORD123!!",
            "ADMIN",
            "A1aB2bC3cD4dE5eF6fG7g",
            "1234;.,/]1234",
        )
        for password in invalid:
            with self.subTest(password=password):
                self.assertFalse(
                    self.user1._check_password_complexity(password, raise_on_failure=False)
                )

        valid = (
            "Sixteenchars12@_",
            "thisis4reallybadPassword!",
            "C0rrecthorsebatteryst@ple",
            "a!A@0£b$B%0^c&C*0(d)D_0+e",
            'Password1234\'"""""',
        )
        for password in valid:
            with self.subTest(password=password):
                self.assertTrue(
                    self.user1._check_password_complexity(password, raise_on_failure=False)
                )
