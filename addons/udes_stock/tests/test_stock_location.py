from .common import BaseUDES
from odoo.exceptions import ValidationError


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
                {"name": "Zone 01", "location_id": cls.stock_location.id, "usage": "view"},
                {"name": "Zone 02", "location_id": cls.stock_location.id, "usage": "view"},
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

    def test_get_common_ancestor_none(self):
        """Test get_common_ancestor with no locations"""
        Location = self.env["stock.location"]

        location = Location.browse()
        self.assertEqual(location, location.get_common_ancestor())

    def test_get_common_ancestor_single(self):
        """Test get_common_ancestor with a single location"""
        location = self.stock_location
        self.assertEqual(location, location.get_common_ancestor())

    def test_get_common_ancestor_multiple_common_parent(self):
        """
        Test get_common_ancestor with multiple locations sharing a common
        parent
        """
        locations = self.loc_01_01 | self.loc_01_02
        self.assertEqual(self.zone_01, locations.get_common_ancestor())

    def test_get_common_ancestor_multiple_including_common_parent(self):
        """
        Test get_common_ancestor with multiple locations sharing a common
        parent, including their common parent in the set
        """
        locations = self.loc_01_01 | self.loc_01_02 | self.zone_01
        self.assertEqual(self.zone_01, locations.get_common_ancestor())

    def test_get_common_ancestor_multiple_common_grandparent(self):
        """
        Test get_common_ancestor with multiple locations sharing a common
        grandparent
        """
        locations = self.loc_01_01 | self.loc_02_02
        self.assertEqual(self.stock_location, locations.get_common_ancestor())

    def test_get_common_ancestor_multiple_no_common_ancestor(self):
        """
        Test get_common_ancestor with multiple locations with no shared ancestry
        """
        Location = self.env["stock.location"]

        physical_locations = self.env.ref("stock.stock_location_locations")
        virtual_locations = self.env.ref("stock.stock_location_locations_virtual")
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
            {"name": "EMPTY", "barcode": "LEMPTY", "location_id": cls.stock_location.id}
        )
        cls.stocked_location = Location.create(
            {"name": "STOCKED", "barcode": "LSTOCKED", "location_id": cls.stock_location.id}
        )
        cls.create_quant(cls.apple.id, cls.stocked_location.id, 10)

        cls.storage_location = Location.create(
            {"name": "STORAGE", "barcode": "LSTORAGE", "location_id": cls.stock_location.id}
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
        cls._setup_countable_locations()

    @classmethod
    def _setup_countable_locations(cls):
        """Create a chain of countable and uncountable locations"""
        # Countable locations
        cls.countable_zone = cls.create_location(
            "Countable Zone", usage="view", u_location_is_countable="yes"
        )
        cls.countable_zone_a = cls.create_location(
            "Zone A", usage="view", location_id=cls.countable_zone.id
        )
        cls.countable_location_a1 = cls.create_location(
            "COUNTA1", location_id=cls.countable_zone_a.id
        )

        # Uncountable locations
        cls.uncountable_zone = cls.create_location(
            "Uncountable Zone", usage="view", u_location_is_countable="no"
        )
        cls.uncountable_zone_a = cls.create_location(
            "Zone A", usage="view", location_id=cls.uncountable_zone.id
        )
        cls.uncountable_location_a1 = cls.create_location(
            "UNCOUNTA1", location_id=cls.uncountable_zone_a.id
        )

    def get_location_with_children(self, locations):
        """Returns the supplied location(s) along with all of their child locations"""
        Location = self.env["stock.location"]
        return Location.search([("id", "child_of", locations.ids)])

    def get_countable_locations(self):
        """Returns all locations in the countable zone"""
        return self.get_location_with_children(self.countable_zone)

    def get_uncountable_locations(self):
        """Returns all locations in the uncountable zone"""
        return self.get_location_with_children(self.uncountable_zone)

    def assert_locations_countable(self, locations):
        """Asserts whether each location supplied is countable"""
        for location in locations:
            with self.subTest(location=location):
                self.assertTrue(
                    location.u_is_countable, f"{location.name} is not countable when it should be"
                )

    def assert_locations_not_countable(self, locations):
        """Asserts whether each location supplied is not countable"""
        for location in locations:
            with self.subTest(location=location):
                self.assertFalse(
                    location.u_is_countable, f"{location.name} is countable when it shouldn't be"
                )

    def test_countable_locations_marked_countable(self):
        """Assert that all locations under countable zone are countable by default"""
        self.assert_locations_countable(self.get_countable_locations())

    def test_uncountable_locations_marked_not_countable(self):
        """Assert that all locations under non-countable zone are not countable by default"""
        self.assert_locations_not_countable(self.get_uncountable_locations())

    def test_updating_parent_updates_children(self):
        """Move a countable zone to the uncountable zone, should no longer be countable"""
        self.countable_zone_a.location_id = self.uncountable_zone
        self.assert_locations_not_countable(self.get_location_with_children(self.countable_zone_a))

    def test_middle_location_updated(self):
        """Check updating middle location in a chain properly updates its children"""
        self.countable_zone_a.u_location_is_countable = "no"

        # Assert the parent is still countable
        self.assert_locations_countable(self.countable_zone)

        # Assert itself and its children are not countable
        self.assert_locations_not_countable(self.get_location_with_children(self.countable_zone_a))


class TestInternalLocationChildrenConstraint(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestInternalLocationChildrenConstraint, cls).setUpClass()
        cls._setup_valid_location_structure()

    @classmethod
    def _setup_valid_location_structure(cls):
        """
        Create a chain of locations with only the bottom level of locations being set as internal
        """
        cls.location_zone = cls.create_location("Location Zone", usage="view")
        cls.location_zone_a = cls.create_location(
            "Zone A", usage="view", location_id=cls.location_zone.id
        )
        cls.location_zone_a1 = cls.create_location(
            "Zone A1", usage="view", location_id=cls.location_zone_a.id
        )

        cls.location_1 = cls.create_location("Loc 1", location_id=cls.location_zone_a1.id)
        cls.location_2 = cls.create_location("Loc 2", location_id=cls.location_zone_a1.id)
        cls.location_3 = cls.create_location("Loc 3", location_id=cls.location_zone_a1.id)

    def test_new_location_cannot_have_internal_parent(self):
        """
        Create a new child location under an internal location,
        ValidationError will be raised to prevent this
        """
        new_location_parent = self.location_1
        new_location_name = "Child of Internal"
        new_location_full_name = f"{new_location_parent.complete_name}/{new_location_name}"

        with self.assertRaises(ValidationError) as e:
            self.create_location("Child of Internal", location_id=new_location_parent.id)
        self.assertEqual(
            e.exception.args[0],
            f"Unable to save location '{new_location_full_name}'."
            " Internal Locations cannot have child locations.",
        )

    def test_location_parent_cannot_be_set_to_internal(self):
        """
        Update an existing location that has children to be internal,
        ValidationError will be raised to prevent this
        """
        location = self.location_zone_a1
        self.assertTrue(
            location.child_ids, f"Location '{location.name}' should have child locations"
        )

        with self.assertRaises(ValidationError) as e:
            location.usage = "internal"
        # Location name will have been recomputed but then reverted when the exception is raised
        location_constraint_name = f"{location.location_id.name}/{location.name}"
        self.assertEqual(
            e.exception.args[0],
            f"Unable to save location '{location_constraint_name}'."
            " Internal Locations cannot have child locations.",
        )


class PickingZoneTestCase(BaseUDES):
    """Tests for picking zone behaviours."""

    def test_returns_location_id_if_location_is_a_picking_zone(self):
        """Test that a location that is a picking zone returns its id for u_picking_zone_id."""
        loc = self.create_location(
            "picking_zone_test_location", location_id=self.stock_location.id, u_is_picking_zone=True
        )
        self.assertEqual(loc.u_picking_zone_id, loc)

    def test_returns_parent_id_if_parent_is_a_picking_zone(self):
        """Test that when a parent location is a picking zone it is returned correctly."""
        loc = self.create_location("picking_zone_test_location", location_id=self.stock_location.id)
        self.stock_location.u_is_picking_zone = True
        self.assertEqual(loc.u_picking_zone_id, self.stock_location)

    def test_returns_false_if_not_within_a_picking_zone(self):
        """Test that when no parent location is a picking zone, u_picking_zone_id is False."""
        loc = self.create_location("picking_zone_test_location", location_id=self.stock_location.id)
        self.assertFalse(loc.u_picking_zone_id)

    def test_returns_closest_zone_in_hierarchy_of_zones(self):
        """Test that a location's picking zone is the closest in the location hierarchy."""
        Location = self.env["stock.location"]

        wh_location = Location.search([("name", "=", "WH")])
        grandparent = self.create_location(
            "picking_zone_test_location_A",
            location_id=wh_location.id,
            u_is_picking_zone=True,
            usage="view",
        )
        parent = self.create_location(
            "picking_zone_test_location_B",
            location_id=grandparent.id,
            u_is_picking_zone=True,
            usage="view",
        )
        location = self.create_location("test_location", location_id=parent.id)

        self.assertEqual(location.u_picking_zone_id, parent)

        (grandparent | parent | location).unlink()
        grandparent = self.create_location(
            "picking_zone_test_location_B",
            location_id=wh_location.id,
            u_is_picking_zone=True,
            usage="view",
        )
        parent = self.create_location(
            "picking_zone_test_location_A",
            location_id=grandparent.id,
            u_is_picking_zone=True,
            usage="view",
        )
        location = self.create_location("test_location", location_id=parent.id)

        self.assertEqual(location.u_picking_zone_id, parent)
