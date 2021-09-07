from . import common


class TestLocationState(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestLocationState, cls).setUpClass()
        cls._setup_state_locations()

    @classmethod
    def _setup_state_locations(cls):
        """
        Setup a location for each state:
            - Blocked (flagged as blocked)
            - Empty (no quants)
            - Has Stock (contains quants)
        """
        Location = cls.env["stock.location"]

        cls.blocked_location = Location.create(
            {
                "name": "BLOCKED",
                "barcode": "LBLOCKED",
                "location_id": cls.stock_location.id,
                "u_blocked": True,
                "u_blocked_reason": "testing",
            }
        )
        cls.empty_location = Location.create(
            {"name": "EMPTY", "barcode": "LEMPTY", "location_id": cls.stock_location.id}
        )
        cls.stocked_location = Location.create(
            {"name": "STOCKED", "barcode": "LSTOCKED", "location_id": cls.stock_location.id}
        )
        for location in cls.blocked_location | cls.stocked_location:
            cls.create_quant(cls.apple.id, location.id, 10)

    def block_location(self, location, reason="testing"):
        """Block each location in self"""
        location.write({"u_blocked": True, "u_blocked_reason": reason})

    def unblock_location(self, location):
        """Unblock each location in self"""
        location.write({"u_blocked": False})

    def remove_stock_from_location(self, location, force=False):
        """
        Remove all stock from the supplied location by completing an inventory adjustment
        where all product quantities are set to zero.

        If force is set to True then a blocked location will be temporarily unblocked and blocked
        again once it has been emptied.
        """
        location.ensure_one()

        blocked_reason = False
        if location.u_blocked and force:
            # temporarily unblock the blocked location
            blocked_reason = location.u_blocked_reason
            self.unblock_location(location)

        inventory_adjustment = self.create_inventory(location)
        inventory_adjustment.action_start()
        # Set product_qty of all lines to 0, which will delete the quants
        inventory_adjustment.line_ids.write({"product_qty": 0})
        inventory_adjustment.action_done()

        if blocked_reason:
            self.block_location(location, reason=blocked_reason)

    def assert_location_state(self, location, expected_state):
        """Assert that the supplied location's state matches the supplied expected state"""
        location.ensure_one()
        state = location.u_state
        error_msg = f"{location.name} state should be: '{expected_state}', got: '{state}'"
        self.assertEqual(state, expected_state, error_msg)

    def test_stock_locations_state_calculated_correctly(self):
        """
        Assert that the location state is correctly calculated for locations
        that are blocked, empty or have stock
        """
        expected_states_by_location = {
            self.blocked_location: "blocked",
            self.empty_location: "empty",
            self.stocked_location: "has_stock",
        }

        for location, expected_state in expected_states_by_location.items():
            with self.subTest(location=location, expected_state=expected_state):
                self.assert_location_state(location, expected_state)

    def test_stock_location_state_updated_to_empty(self):
        """
        Assert that the state field is correctly recalculated for locations with stock
        that have their stock removed
        """
        # Blocked locations that are emptied should still be in a blocked state
        expected_states_by_location = {
            self.blocked_location: "blocked",
            self.stocked_location: "empty",
        }

        for location, expected_state in expected_states_by_location.items():
            # Empty the location
            self.remove_stock_from_location(location, force=True)
            with self.subTest(location=location, expected_state=expected_state):
                self.assert_location_state(location, expected_state)

    def test_stock_location_state_updated_to_has_stock(self):
        """
        Assert that the state field is correctly recalculated for empty locations
        that have stock added
        """
        # Add some stock to the empty location
        self.create_quant(self.apple.id, self.empty_location.id, 10)

        # Assert that the previously empty location's state is now has_stock
        self.assert_location_state(self.empty_location, "has_stock")

    def test_stock_location_state_updated_to_blocked(self):
        """
        Assert that the state field is correctly recalculated for locations
        with and without stock that become blocked or unblocked
        """
        expected_states_by_location_blocked = {
            self.empty_location: "blocked",
            self.stocked_location: "blocked",
        }

        for location, expected_state in expected_states_by_location_blocked.items():
            # Block the location
            self.block_location(location)
            with self.subTest(location=location, expected_state=expected_state):
                self.assert_location_state(location, expected_state)

        expected_states_by_location_unblocked = {
            self.empty_location: "empty",
            self.stocked_location: "has_stock",
        }

        for location, expected_state in expected_states_by_location_unblocked.items():
            # Unblock the location
            self.unblock_location(location)
            with self.subTest(location=location, expected_state=expected_state):
                self.assert_location_state(location, expected_state)
