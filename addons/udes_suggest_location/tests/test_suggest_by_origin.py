"""Testcases for the "by_origin" policy."""
from . import common
from ..registry.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY


class TestSuggestByOrigin(common.SuggestedLocations):
    """
    Tests for the by origin policy.

    If the policy is enabled, once a picking for a particular origin has been
    completed, the drop off location for this picking should be suggested for
    all subsequent pickings with the same origin.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        policy_name = "by_origin"
        cls.ByOrigin = SUGGEST_LOCATION_REGISTRY[policy_name](cls.env)
        # Set suggested locations policy to "by origin"
        cls.picking_type_pick.u_suggest_locations_policy = policy_name
        # Create quants
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 10)
        cls.create_quant(cls.cherry.id, cls.test_stock_location_03.id, 10)
        cls.create_quant(cls.damson.id, cls.test_stock_location_04.id, 10)
        # Create pickings
        origin = "SO0001"
        cls.origin = origin
        products_info1 = [{"product": cls.apple, "qty": 4}]
        products_info2 = [{"product": cls.banana, "qty": 4}, {"product": cls.cherry, "qty": 10}]
        products_info3 = [{"product": cls.damson, "qty": 4}]
        cls.picking1 = cls.create_picking(
            cls.picking_type_pick,
            products_info=products_info1,
            origin=origin,
            confirm=True,
            assign=True,
        )
        cls.picking2 = cls.create_picking(
            cls.picking_type_pick,
            products_info=products_info2,
            origin=origin,
            confirm=True,
            assign=True,
        )
        cls.picking3 = cls.create_picking(
            cls.picking_type_pick,
            products_info=products_info3,
            origin="SO0002",
            confirm=True,
            assign=True,
        )
        cls.mls = (
            cls.picking1.move_line_ids | cls.picking2.move_line_ids | cls.picking3.move_line_ids
        )

    def test_extracts_origin_and_location_from_mls(self):
        """Get the origin and location destination from move lines"""
        expected = {
            "location": self.check_location,
            "origin": "SO0001",
        }

        vals = self.ByOrigin.get_values_from_mls(
            self.mls.filtered(lambda ml: ml.picking_id.origin == self.origin)
        )

        self.assertEqual(vals, expected)

    def test_raises_error_if_multiple_origins(self):
        """Fail to get details due to multiple origins given"""
        with self.assertRaises(ValueError) as e:
            self.ByOrigin.get_values_from_mls(self.mls)
        self.assertEqual(str(e.exception), "Expected single origin, got: ['SO0001', 'SO0002']")

    def test_retrieves_origin_and_location_from_dict(self):
        """Check that get values returns the correct dict"""
        expected = {
            "location": self.check_location,
            "origin": "SO0001",
        }

        values = self.ByOrigin.get_values_from_dict(
            self.picking1.move_lines._prepare_move_line_vals()
        )

        self.assertEqual(values, expected)

    def test_suggests_location_for_origin(self):
        """Get locations based on origin and location"""
        # Get locations based on origin and location
        self.complete_picking(self.picking1)

        locs = self.ByOrigin.get_locations(self.origin, self.check_location)

        self.assertEqual(locs, self.test_check_location_01)

    def test_suggests_all_locations_if_no_processed_picking(self):
        # Return no locations if no origin in child locations
        self.assertEqual(len(self.ByOrigin.get_locations("SO0002", self.check_location)), 0)

    def test_suggests_different_location_for_different_origin(self):
        self.complete_picking(self.picking1)
        locs = self.ByOrigin.get_locations("SO0002", self.check_location)
        self.assertEqual(len(locs), 0)
