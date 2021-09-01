from . import common


class TestLocationCountable(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestLocationCountable, cls).setUpClass()
        cls.Location = cls.env["stock.location"]

        cls.investigation_location = cls.env.ref("udes_stock.location_stock_investigation")
        cls.investigation_1 = cls.Location.create({
            'name': "INVESTIGATION_1",
            'barcode': "LTESTINVEST1",
            'location_id': cls.investigation_location.id,
        })

        cls.stock_location.u_location_is_countable = "yes"
        cls.investigation_location.u_location_is_countable = "no"
        cls.test_location_02.location_id = cls.test_location_01.id

    def assert_location_countable(self, locations):
        for location in locations:
            with self.subTest(location=location):
                self.assertTrue(
                    location.u_is_countable, f"{location.name} is not countable when it should be"
                )

    def assert_location_not_countable(self, locations):
        for location in locations:
            with self.subTest(location=location):
                self.assertFalse(
                    location.u_is_countable, f"{location.name} is countable when it shouldn't be"
                )

    def test_stock_locations_countable(self):
        """Assert that all locations under stock are countable by default"""
        stock_locations = self.Location.search([("id", "child_of", self.stock_location.id)])
        self.assert_location_countable(stock_locations)

    def test_stock_investigation_locations_not_countable(self):
        """Test to see if investigation locations are not countable."""
        stock_investigation_locations = self.Location.search(
            [("id", "child_of", self.investigation_location.id)]
        )
        self.assert_location_not_countable(stock_investigation_locations)

    def test_updating_parent_updates_children(self):
        """Updating parents, testing if it affects the children"""
        # Move test location 1 underneath investigation which is not countable
        self.test_location_01.location_id = self.investigation_location.id
        self.assert_location_not_countable(self.test_locations)

    def test_countable_default_false(self):
        """Check if u_is_countable defaults to false"""
        self.stock_location.u_location_is_countable = False
        self.assert_location_not_countable(self.stock_location)

    def test_middle_location_updated(self):
        """Check updating middle location in a chain properly updates its children"""
        self.test_location_01.u_location_is_countable = "no"

        self.assert_location_not_countable(self.test_location_02)
        self.assert_location_countable(self.stock_location)
