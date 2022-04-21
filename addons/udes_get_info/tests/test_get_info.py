"""Unit tests for the get_info method's generic behaviour."""
import pprint
from . import common
from ..models.models import BASIC_GET_INFO_VALUES


class TestGetInfo(common.BaseTestCase):
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
                "barcode": "LTESTGRANDCHILD",
                "location_id": cls.child_location.id,
            }
        )
        cls.family_tree = (cls.grandchild_location, cls.child_location, cls.stock_location)

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
        # Run checks via helper
        info = self.grandchild_location.get_info(level=3, extra_fields={"location_id"})[0]
        self._recursive_field_helper("location_id", info, self.family_tree)

    def test_get_info_with_custom_fields(self):
        """Check the info returned with custom fields"""
        # Define fields to search
        test_fields = {"location_id", "name"}
        # Run checks via helper
        info = self.grandchild_location.get_info(level=3, info_fields=test_fields)[0]
        # Check the fields at each level
        self._recursive_field_helper("location_id", info, self.family_tree)
        self.assertEqual(test_fields, set(info.keys()))

    def test_get_info_with_different_recursion(self):
        """Check the level does the correct amount of recursions"""
        # Define fields to search for simplicity
        test_fields = {"location_id", "name"}
        # Run checks via helper
        info_level1 = self.grandchild_location.get_info(level=1, info_fields=test_fields)[0]
        info_level3 = self.grandchild_location.get_info(level=3, info_fields=test_fields)[0]
        # Check no entries with level 1 has a dictionary
        self.assertTrue(any(isinstance(val, dict) for val in info_level1.values()))
        # Check the amount of recursions for the different level values
        self.assertEqual(self._count_nested_dict_by_key(info_level1, "location_id"), 1)
        self.assertEqual(self._count_nested_dict_by_key(info_level3, "location_id"), 3)

    def test_logs_names_of_models_with_missing_fields(self):
        """The system will log missing fields and their associated models."""
        with self.assertLogs("odoo.addons.udes_get_info.models.models", level="DEBUG") as cm:
            self.grandchild_location.get_info(extra_fields={"spam"})
        self.assertEqual(
            cm.output,
            [
                "DEBUG:odoo.addons.udes_get_info.models.models:Cannot find field name 'spam' on model 'stock.location'"
            ],
        )

    def test_retrieves_expected_fields_from_related_model(self):
        """The system will retrieve the fields defined on related models."""
        apple = self.create_product(name="Apple")
        quant = self.create_quant(
            apple.id, self.grandchild_location.id, 1, package_id=self.create_package().id
        )

        # TODO Use explicit sets here.
        expected_quant_fields = BASIC_GET_INFO_VALUES | quant._get_info_field_names
        expected_quant_fields.remove("name")  # quants don't have names
        expected_apple_fields = BASIC_GET_INFO_VALUES | apple._get_info_field_names

        info = quant.get_info()[0]
        self.assertSetEqual(set(info.keys()), expected_quant_fields)
        self.assertSetEqual(set(info["product_id"].keys()), expected_apple_fields)

    def test_returns_only_scalar_fields_at_level_0(self):
        """At level 0, info for related fields is not retrieved."""
        apple = self.create_product(name="Apple")
        quant = self.create_quant(
            apple.id, self.grandchild_location.id, 1, package_id=self.create_package().id
        )

        info = quant.get_info(level=0)[0]

        self.assertTrue(
            all(isinstance(v, (int, float, str)) for v in info.values()),
            msg=f"{pprint.pformat(info)}",
        )

    def test_returns_top_level_related_fields_at_level_1(self):
        """At level 1, info for related fields in the top-level model is retrieved."""
        info = self.grandchild_location.get_info(level=1, extra_fields={"location_id"})[0]
        second_level_info = info["location_id"]

        self.assertTrue(
            all(isinstance(v, (int, str)) for v in second_level_info.values()),
            msg=f"{pprint.pformat(info)}",
        )

    def test_returns_second_level_related_fields_at_level_2(self):
        """At level 2, info for related fields in the top-level model, and the next level is retrieved."""
        info = self.grandchild_location.get_info(level=2, extra_fields={"location_id"})[0]
        third_level_info = info["location_id"]["location_id"]

        self.assertTrue(
            all(isinstance(v, (int, str)) for v in third_level_info.values()),
            msg=f"{pprint.pformat(info)}",
        )

    def test_respects_extra_fields_in_related_models(self):
        """Info for the target model and related models will contain extra fields if available."""
        package = self.create_package()
        assert not package.location_id
        apple = self.create_product(name="Apple")
        quant = self.create_quant(apple.id, self.grandchild_location.id, 1, package_id=package.id)

        assert package.location_id
        info = quant.get_info(level=2, extra_fields={"location_id"})[0]
        package_info = info["package_id"]

        self.assertIn("location_id", info)
        self.assertIn("location_id", package_info)

    def test_returns_alternative_name_if_provided(self):
        """If we provide an alternative name it is used instead of the attribute name."""
        info = self.grandchild_location.get_info(info_fields={("stripes", "barcode")})[0]

        self.assertNotIn("barcode", info)
        self.assertEqual(info["stripes"], "LTESTGRANDCHILD")
