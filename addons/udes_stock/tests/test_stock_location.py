from .common import BaseUDES


class TestStockLocation(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockLocation, cls).setUpClass()

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
        virtual_locations = self.env.ref("stock.stock_location_locations_virtual")
        locations = physical_locations | virtual_locations
        self.assertEqual(Location.browse(), locations.get_common_ancestor())
