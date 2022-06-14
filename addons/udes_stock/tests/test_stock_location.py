import unittest
from .common import BaseUDES


class TestStockLocation(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Location = cls.env["stock.location"]

        # Create two zones under stock, containing two sublocations each:
        # Stock > Zone 01 > Loc 01-01
        # Stock > Zone 01 > Loc 01-02
        # Stock > Zone 02 > Loc 02-01
        # Stock > Zone 02 > Loc 02-02
        cls.zone_01, cls.zone_02 = Location.create(
            [
                {"name": "Zone 01", "location_id": cls.stock_location.id},
                {"name": "Zone 02", "location_id": cls.stock_location.id},
            ]
        )
        cls.loc_01_01, cls.loc_01_02, cls.loc_02_01, cls.loc_02_02 = Location.create(
            [
                {"name": "Loc 01-01", "location_id": cls.zone_01.id},
                {"name": "Loc 01-02", "location_id": cls.zone_01.id},
                {"name": "Loc 02-01", "location_id": cls.zone_02.id},
                {"name": "Loc 02-02", "location_id": cls.zone_02.id},
            ]
        )

    def test01_get_common_ancestor_none(self):
        """Test get_common_ancestor with no locations"""
        Location = self.env["stock.location"]

        location = Location.browse()
        self.assertEqual(location, location.get_common_ancestor())

    def test02_get_common_ancestor_single(self):
        """Test get_common_ancestor with a single location"""
        location = self.stock_location
        self.assertEqual(location, location.get_common_ancestor())

    def test03_get_common_ancestor_multiple_common_parent(self):
        """
        Test get_common_ancestor with multiple locations sharing a common
        parent
        """
        locations = self.loc_01_01 | self.loc_01_02
        self.assertEqual(self.zone_01, locations.get_common_ancestor())

    def test04_get_common_ancestor_multiple_including_common_parent(self):
        """
        Test get_common_ancestor with multiple locations sharing a common
        parent, including their common parent in the set
        """
        locations = self.loc_01_01 | self.loc_01_02 | self.zone_01
        self.assertEqual(self.zone_01, locations.get_common_ancestor())

    def test05_get_common_ancestor_multiple_common_grandparent(self):
        """
        Test get_common_ancestor with multiple locations sharing a common
        grandparent
        """
        locations = self.loc_01_01 | self.loc_02_02
        self.assertEqual(self.stock_location, locations.get_common_ancestor())

    def test06_get_common_ancestor_multiple_no_common_ancestor(self):
        """
        Test get_common_ancestor with multiple locations with no shared ancestry
        """
        Location = self.env["stock.location"]

        physical_locations = self.env.ref("stock.stock_location_locations")
        virtual_locations = self.env.ref(
            "stock.stock_location_locations_virtual")
        locations = physical_locations | virtual_locations
        self.assertEqual(Location.browse(), locations.get_common_ancestor())


class TestLocationState(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestLocationState, cls).setUpClass()
        cls._setup_state_locations()

    @classmethod
    def _setup_state_locations(cls):
        """
        Make stock_location countable to cascade to children.
        Setup a location for each state:
            - Empty (no quants)
            - Has Stock (contains quants)
        Create another location to move stock into for tests.
        """
        Location = cls.env["stock.location"]

        cls.stock_location.u_location_is_countable = "yes"
        cls.empty_location = Location.create(
            {"name": "EMPTY", "barcode": "LEMPTY",
                "location_id": cls.stock_location.id}
        )
        cls.stocked_location = Location.create(
            {"name": "STOCKED", "barcode": "LSTOCKED",
                "location_id": cls.stock_location.id}
        )
        cls.create_quant(cls.apple.id, cls.stocked_location.id, 10)

        cls.storage_location = Location.create(
            {"name": "STORAGE", "barcode": "LSTORAGE",
                "location_id": cls.stock_location.id}
        )

    def remove_stock_from_location(self, location):
        """
        Remove all stock from the supplied location by moving them into the
        storage location.
        """
        location.ensure_one()

        Quant = self.env["stock.quant"]
        quants = Quant.search([("location_id", "=", location.id)])
        quants.write({"location_id": self.storage_location.id})

    def test_stock_locations_state_calculated_correctly(self):
        """
        Assert that the location state is correctly calculated for locations
        that are blocked, empty or have stock
        """
        expected_states_by_location = {
            self.empty_location: "empty",
            self.stocked_location: "has_stock",
        }

        for location, expected_state in expected_states_by_location.items():
            with self.subTest(location=location, expected_state=expected_state):
                self.assertEqual(location.u_countable_state, expected_state)

    def test_countable_state_is_blanked_when_locations_are_not_countable(self):
        """Assert that when the location is not countable the countable state location is False"""
        self.stock_location.u_is_countable = False

        for location in self.empty_location | self.stocked_location:
            with self.subTest(location=location.name):
                self.assertFalse(location.u_is_countable)
                self.assertFalse(location.u_countable_state)

    def test_stock_location_state_updated_to_empty(self):
        """
        Assert that the state field is correctly recalculated for locations with stock
        that have their stock removed
        """
        self.assertEqual(self.stocked_location.u_countable_state, "has_stock")
        self.remove_stock_from_location(self.stocked_location)
        self.assertEqual(self.stocked_location.u_countable_state, "empty")

    def test_stock_location_state_updated_to_has_stock(self):
        """
        Assert that the state field is correctly recalculated for empty locations
        that have stock added
        """
        self.assertEqual(self.empty_location.u_countable_state, "empty")
        self.create_quant(self.apple.id, self.empty_location.id, 10)
        self.assertEqual(self.empty_location.u_countable_state, "has_stock")

    def test_toggle_archived_state_on_activation(self):
        """When we toggle the active state of a location the state is recomputed."""
        self.empty_location.active = False
        self.assertEqual(self.empty_location.u_countable_state, "archived")
        self.empty_location.active = True
        self.assertEqual(self.empty_location.u_countable_state, "empty")


class TestLocationCountable(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestLocationCountable, cls).setUpClass()
        cls.Location = cls.env["stock.location"]

        cls.investigation_location = cls.env.ref(
            "udes_stock.location_stock_investigation")
        cls.investigation_1 = cls.Location.create(
            {
                "name": "INVESTIGATION_1",
                "barcode": "LTESTINVEST1",
                "location_id": cls.investigation_location.id,
            }
        )

        # Make stock countable but investaigation not
        cls.stock_location.u_location_is_countable = "yes"
        cls.investigation_location.u_location_is_countable = "no"
        # Make the stock locations into a parent chain
        cls.test_stock_location_02.location_id = cls.test_stock_location_01.id
        cls.test_stock_location_03.location_id = cls.test_stock_location_02.id
        cls.test_stock_location_04.location_id = cls.test_stock_location_03.id

    def assert_locations_countable(self, locations):
        for location in locations:
            with self.subTest(location=location):
                self.assertTrue(
                    location.u_is_countable, f"{location.name} is not countable when it should be"
                )

    def assert_locations_not_countable(self, locations):
        for location in locations:
            with self.subTest(location=location):
                self.assertFalse(
                    location.u_is_countable, f"{location.name} is countable when it shouldn't be"
                )

    def test_stock_locations_countable(self):
        """Assert that all locations under stock are countable by default"""
        stock_locations = self.Location.search(
            [("id", "child_of", self.stock_location.id)])
        self.assert_locations_countable(stock_locations)

    def test_stock_investigation_locations_not_countable(self):
        """Test to see if investigation locations are not countable."""
        stock_investigation_locations = self.Location.search(
            [("id", "child_of", self.investigation_location.id)]
        )
        self.assert_locations_not_countable(stock_investigation_locations)

    def test_updating_parent_updates_children(self):
        """Updating parents, testing if it affects the children"""
        # Move test location 1 underneath investigation which is not countable
        self.test_stock_location_01.location_id = self.investigation_location.id
        self.assert_locations_not_countable(self.test_stock_locations)

    def test_countable_default_false(self):
        """Check if u_is_countable defaults to false"""
        self.stock_location.u_location_is_countable = False
        self.assert_locations_not_countable(
            self.stock_location | self.test_stock_locations)

    def test_middle_location_updated(self):
        """Check updating middle location in a chain properly updates its children"""
        self.test_stock_location_01.u_location_is_countable = "no"

        # Assert the parent is still countable
        self.assert_locations_countable(self.stock_location)

        # Assert itself and its children are not
        self.assert_locations_not_countable(self.test_stock_locations)
