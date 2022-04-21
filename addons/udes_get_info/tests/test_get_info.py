from . import common
from ..models.models import BASIC_GET_INFO_VALUES
from collections import Counter


class TestStockLocation(common.BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Location = cls.env["stock.location"]
        # Get stock location
        cls.stock_location = Location.search([]).filtered(lambda l: l.name == "Stock")
        # Create a child and grandchild location of stock_location
        cls.child_location = Location.create(
            {
                "name": "Test stock location child",
                "barcode": "LSTESTCHILD",
                "location_id": cls.stock_location.id,
            }
        )
        cls.grandchild_location = Location.create(
            {
                "name": "Test stock location grandchild",
                "barcode": "LSTESTGRANDCHILD",
                "location_id": cls.child_location.id,
            }
        )
        cls.family_tree = (cls.grandchild_location, cls.child_location, cls.stock_location)

    def tearDown(self):  # noqa: D102
        Location = self.env["stock.location"]

        # FIXME Some tests add location_id directly to the model's set of
        # fields, but this breaks the mixin test for locations because
        # location_id is not expected in the default return value.
        # For now, make sure we remove 'location_id' after adding it.
        Location._get_info_field_names.discard("location_id")

    def _count_nested_dict_by_key(self, d, key):
        """Helper to count the number of nested dictionaries by key"""
        count = int(key in d)
        val = d.get(key)
        if isinstance(val, dict):
            count += self._count_nested_dict_by_key(val, key)
        return count

    def _comparison_helper(self, info, location):
        """Helper function to check the info against the location
        :params:
            info: an entry in the returned list from get_info
            location: The location to compare against
        """
        for field, val in info.items():
            if isinstance(val, dict):
                # Skip if the value is a dictionary
                continue
            self.assertEqual(val, location[field])

    def _recursive_field_helper(self, field, all_info, family_tree):
        """Helper function to iterate through the (possibly) nested dictionary returned by
        get_info. For simplicity it only looks through the nesting of one field,
        e.g child_ids.
        :params:
            field: The field that controls the nesting
            all_info: The complete dnested dictionary
            familty_tree: The expected tuple of what to compare against. For example
                if looking at child_ids of location, would expect a tuple of
                (grandparent, parent, child)
        """
        for i, _loc in enumerate(family_tree):
            self._comparison_helper(all_info, family_tree[i])
            all_info = all_info.get(field)

    def _check_fields_helper(self, fields, info):
        """Helper function to check all of the nested dictionary has the correct fields
        :params:
            fields: The fields that are expected in the nesting
            info: The complete nested dictionary
        """
        if not any(isinstance(val, dict) for val in info.values()):
            fields = BASIC_GET_INFO_VALUES
        for key, val in info.items():
            if isinstance(val, dict):
                self._check_fields_helper(fields, val.copy())
            self.assertIn(key, fields)

    def test_get_info_simple(self):
        """Simple test to check that the information from get_info is correct for a single
        location with default settings
        """
        self._comparison_helper(self.grandchild_location.get_info()[0], self.grandchild_location)

    def test_check_keys(self):
        """Check we get the expected keys from the _get_info_field_names field"""
        total_info_fields = self.grandchild_location._get_info_field_names | BASIC_GET_INFO_VALUES
        location_info_fields = set(self.grandchild_location.get_info()[0].keys())
        self.assertTrue(location_info_fields.issubset(total_info_fields))

    def test_get_info_with_additional_levels_simple(self):
        """Check the recursion levels by adding field to default fields"""
        # Add location_id to _get_info_field_names
        Location = self.env["stock.location"]
        Location._get_info_field_names.add("location_id")
        # Run checks via helper
        info = self.grandchild_location.get_info(max_level=3)[0]
        self._recursive_field_helper("location_id", info, self.family_tree)

    def test_get_info_with_custom_fields(self):
        """Check the info returned with custom fields"""
        # FIXME we shouldn't need to add location_id to _get_info_field_names
        # for this test to work?
        # Add location_id to _get_info_field_names
        Location = self.env["stock.location"]
        Location._get_info_field_names.add("location_id")
        # Define fields to search
        test_fields = {"location_id", "name"}
        # Run checks via helper
        info = self.grandchild_location.get_info(max_level=3, info_fields=test_fields)[0]
        # Check the fields at each level
        self._recursive_field_helper("location_id", info, self.family_tree)
        self.assertEqual(test_fields, set(info.keys()))

    def test_get_info_with_different_recursion(self):
        """Check the max_level does the correct amount of recursions"""
        # FIXME we shouldn't need to add location_id to _get_info_field_names
        # for this test to work?
        # Add location_id to _get_info_field_names
        Location = self.env["stock.location"]
        Location._get_info_field_names.add("location_id")
        # Define fields to search for simplicity
        test_fields = {"location_id", "name"}
        # Run checks via helper
        info_level1 = self.grandchild_location.get_info(max_level=1, info_fields=test_fields)[0]
        info_level3 = self.grandchild_location.get_info(max_level=3, info_fields=test_fields)[0]
        # Check no entries with level 1 has a dictionary
        self.assertTrue(any(isinstance(val, dict) for val in info_level1.values()))
        # Check the amount of recursions for the different max_level values
        self.assertEqual(self._count_nested_dict_by_key(info_level1, "location_id"), 1)
        self.assertEqual(self._count_nested_dict_by_key(info_level3, "location_id"), 3)

    def test_logs_names_of_models_with_missing_fields(self):
        """The system will log missing fields and their associated models."""
        with self.assertLogs("odoo.addons.udes_get_info.models.models", level="WARNING") as cm:
            self.grandchild_location.get_info(extra_fields={"spam"})
        self.assertEqual(
            cm.output,
            [
                "WARNING:odoo.addons.udes_get_info.models.models:Cannot find field name 'spam' on model 'stock.location'"
            ],
        )
