from odoo.exceptions import ValidationError
from .common import BaseBlocked


class TestStockLocation(BaseBlocked):
    def test_check_blocked_wrong_prefix_type(self):
        """Call check blocked with wrong prefix type will
        raise a ValidationError.

        Prefix is expected to be a string.
        """
        with self.assertRaises(ValidationError) as e:
            self.test_location_01.check_blocked(prefix=7)

        self.assertEqual(e.exception.args[0], "Prefix parameter for check_blocked should be string")

    def test_check_blocked_one_location_one_blocked_location(self):
        """Block test_location_01 and check if it is blocked, which will
        raise a ValidationError.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True

        with self.assertRaises(ValidationError) as e:
            self.test_location_01.check_blocked()

        self.assertEqual(
            e.exception.args[0],
            " Location %s is blocked (reason: %s)."
            " Please speak to a team leader to resolve the issue."
            % (self.test_location_01.name, self.test_location_01.u_blocked_reason),
        )

    def test_check_blocked_two_locations_one_blocked_location(self):
        """Block test_location_01 and check if either test_location_01
        or test_location_02 are blocked, which will raise a
        ValidationError.
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True

        with self.assertRaises(ValidationError) as e:
            self.test_locations.check_blocked()

        self.assertEqual(
            e.exception.args[0],
            " Location %s is blocked (reason: %s)."
            " Please speak to a team leader to resolve the issue."
            % (self.test_location_01.name, self.test_location_01.u_blocked_reason),
        )

    def test_prepare_blocked_msg_blocked_location_no_reason(self):
        """Prepare the message of a blocked location without reason."""
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        msg = self.test_location_01._prepare_blocked_msg()
        self.assertEqual(
            msg,
            "Location %s is blocked (reason: %s)."
            % (self.test_location_01.name, self.test_location_01.u_blocked_reason),
        )

    def test_prepare_blocked_msg_blocked_location_with_reason(self):
        """Prepare the message of a blocked location with reason."""
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        msg = self.test_location_01._prepare_blocked_msg()
        self.assertEqual(
            msg,
            "Location %s is blocked (reason: %s)."
            % (self.test_location_01.name, self.test_location_01.u_blocked_reason),
        )

    def test_prepare_blocked_msg_non_blocked_location(self):
        """Prepare the message of a non blocked location."""
        msg = self.test_location_01._prepare_blocked_msg()
        self.assertEqual(msg, "Location %s is not blocked." % self.test_location_01.name)

    def test_onchange_blocked_to_false(self):
        """Check that blocked reason becomes empty when the
        location is unblocked
        """
        self.test_location_01.u_blocked_reason = "Stock Damaged"
        self.test_location_01.u_blocked = True
        msg = self.test_location_01._prepare_blocked_msg()
        self.assertEqual(
            msg,
            "Location %s is blocked (reason: %s)."
            % (self.test_location_01.name, self.test_location_01.u_blocked_reason),
        )

        self.test_location_01.u_blocked = False
        # simulate the triggering of the onchange
        self.test_location_01.onchange_u_blocked()
        self.assertEqual(self.test_location_01.u_blocked_reason, "")

    def test_check_reserved_quants(self):
        """Blocking a location with reserved quants will raise an error."""
        self.create_quant(self.apple.id, self.test_location_01.id, 10, reserved_quantity=10)

        with self.assertRaises(ValidationError) as e:
            self.test_location_01.u_blocked_reason = "Stock Damaged"
            self.test_location_01.u_blocked = True

        self.assertEqual(
            e.exception.args[0], "Location cannot be blocked because it contains reserved stock."
        )

    def test_check_blocked_reason(self):
        """Blocking a location with no reason given will raise and error"""

        with self.assertRaises(ValidationError) as e:
            self.test_location_01.u_blocked = True

        self.assertEqual(
            e.exception.args[0],
            "A reason for blocking the locations is required when attempting to block a location.",
        )
