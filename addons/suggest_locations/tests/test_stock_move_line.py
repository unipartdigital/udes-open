# -*- coding: utf-8 -*-
from . import common
from ..models.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY
from odoo.exceptions import ValidationError
from unittest.mock import patch, call


class TestStockMoveLine(common.SuggestedLocations):
    @classmethod
    def setUpClass(cls):
        super(TestStockMoveLine, cls).setUpClass()
        cls.MoveLine = cls.env["stock.move.line"]
        # Set policies, use by_product for pick and match_move_line for goods out
        # By default preprocessing is: False for by_product and True match_move_line
        cls.picking_type_pick.u_suggest_locations_policy = "by_product"
        cls.picking_type_goods_out.u_suggest_locations_policy = "match_move_line"
        cls.ByProduct = SUGGEST_LOCATION_REGISTRY["by_product"](cls.env)
        cls.ByMLS = SUGGEST_LOCATION_REGISTRY["match_move_line"](cls.env)

        # Create quants for picking and suggested location
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 10)
        cls.create_quant(cls.apple.id, cls.test_goodsout_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_goodsout_location_02.id, 10)
        cls.create_quant(cls.apple.id, cls.test_goodsout_location_03.id, 10)
        cls.create_quant(cls.apple.id, cls.test_trailer_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_trailer_location_02.id, 10)
        cls.create_quant(cls.apple.id, cls.test_trailer_location_03.id, 10)

        # Create picking
        cls._pick_info = [{"product": cls.banana, "qty": 5}, {"product": cls.apple, "qty": 5}]
        cls.picking_pick = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True, assign=True,
        )
        cls.picking_out = cls.create_picking(
            cls.picking_type_goods_out, products_info=cls._pick_info, confirm=True, assign=True,
        )
        cls.pick_mls = cls.picking_pick.move_line_ids
        cls.out_mls = cls.picking_out.move_line_ids
        # Make the out and trailer locations a view
        cls.out_location.usage = "view"
        cls.trailer_location.usage = "view"

        # Destination locations for each product
        cls.pick_apple_locs = cls.test_goodsout_location_01 | cls.test_goodsout_location_03
        pick_empty_locs = cls.test_goodsout_location_04
        cls.pick_all_locs = cls.pick_apple_locs | pick_empty_locs
        cls.out_apple_locs = cls.test_trailer_location_01
        out_empty_locs = cls.test_trailer_location_04
        cls.out_all_locs = cls.out_apple_locs | out_empty_locs

        # Particular movelines for pick and goods out
        cls.pick_apple_mls = cls.pick_mls.filtered(lambda ml: ml.product_id == cls.apple)
        cls.pick_banana_mls = cls.pick_mls.filtered(lambda ml: ml.product_id == cls.banana)
        cls.out_apple_mls = cls.out_mls.filtered(lambda ml: ml.product_id == cls.apple)

        # Mock functions, for suggest locations and validate
        # Suggest locations return empty locations
        cls.mock_suggested_locations_pick = patch.object(
            cls.MoveLine.__class__, "suggest_locations", return_value=cls.test_goodsout_location_04,
        )
        cls.mock_suggested_locations_out = patch.object(
            cls.MoveLine.__class__, "suggest_locations", return_value=cls.test_trailer_location_04,
        )
        cls.mock_validate_location_dest = patch.object(
            cls.MoveLine.__class__, "validate_location_dest", return_value=None
        )

    def test01_get_policy_class(self):
        """Check policy class returns the correct class"""
        # Fetch by product policy
        by_product = self.MoveLine._get_policy_class(self.picking_type_pick)
        # Check namin and preprocessing values
        self.assertEqual(by_product.name(), "by_product")
        self.assertFalse(by_product.preprocessing)
        match_ml_policy = self.MoveLine._get_policy_class(self.picking_type_goods_out)
        self.assertEqual(match_ml_policy.name(), "match_move_line")
        self.assertTrue(match_ml_policy.preprocessing)
        # Check error raised when no policy found
        with self.assertRaises(ValueError) as e:
            self.MoveLine._get_policy_class(self.picking_type_internal)
        self.assertEqual(str(e.exception), f"Policy with name=False could not be found")

    def test02_suggest_locations_errors_with_not_enough_info(self):
        """Suggest locations by picking type should throw error when not enough information is
        given
        """
        #  Error as no values given
        with self.assertRaises(ValueError) as e:
            self.MoveLine.suggest_locations()
        self.assertEqual(
            str(e.exception),
            "Missing information to suggest locations, please provide either move "
            + "lines or picking and values!",
        )
        # Error as only picking given
        with self.assertRaises(ValueError) as e:
            self.MoveLine.suggest_locations(picking=self.picking_pick)
        self.assertEqual(
            str(e.exception),
            "Missing information to suggest locations, please provide either move "
            + "lines or picking and values!",
        )
        #  Error as only values given
        values = {"product_id": self.apple.id, "picking": self.picking_pick.id}
        with self.assertRaises(ValueError) as e:
            self.MoveLine.suggest_locations(values=values)
        self.assertEqual(
            str(e.exception),
            "Missing information to suggest locations, please provide either move "
            + "lines or picking and values!",
        )

    def test03_suggest_locations_errors_with_no_location_policy(self):
        """Suggest locations by picking type should throw an error when the locations policy is
        not set
        """
        #  Error as no location policy set
        with self.assertRaises(ValueError) as e:
            # Set policy to None
            self.picking_type_pick.u_suggest_locations_policy = None
            self.pick_apple_mls.suggest_locations()
        self.assertEqual(str(e.exception), "No policy set")

    def test04_suggest_locations_via_self_by_product(self):
        """Get the suggest locations via self for by product policy, looping through all
        drop location constraints for completeness
        """
        #  Get locations to drop off apples
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = self.pick_apple_mls.suggest_locations()
            self.assertEqual(locs, self.pick_apple_locs)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = self.pick_apple_mls.suggest_locations()
            self.assertEqual(locs, self.pick_all_locs)

    def test05_suggest_locations_via_self_by_match_move_line(self):
        """Get the suggest locations via self for match by move line, looping through all
        drop location constraints for completeness
        """
        # Write the dest location for apple mls
        self.out_apple_mls.location_dest_id = self.test_trailer_location_01
        #  Get locations to drop off apples
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            self.picking_type_goods_out.u_drop_location_constraint = drop_constraint
            locs = self.out_apple_mls.suggest_locations()
            self.assertEqual(locs, self.out_apple_locs)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            self.picking_type_goods_out.u_drop_location_constraint = drop_constraint
            locs = self.out_apple_mls.suggest_locations()
            self.assertEqual(locs, self.out_all_locs)

    def test06_suggest_locations_via_picking_and_values_by_product(self):
        """Get the suggest locations by picking and values, not self
        This is set up for 'by_product' policy and loop through all u_drop_location_constraint
        for completeness
        """
        #  Get locations to drop off apples
        values = {"product_id": self.apple.id, "picking_id": self.picking_pick.id}
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = self.MoveLine.suggest_locations(picking=self.picking_pick, values=values)
            self.assertEqual(locs, self.pick_apple_locs)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = self.MoveLine.suggest_locations(picking=self.picking_pick, values=values)
            self.assertEqual(locs, self.pick_all_locs)

    def test07_suggest_locations_via_picking_and_values_match_move_line(self):
        """Get the suggest locations by picking and values, not self.
        This is set up for 'match_move_line' policy and loop through all u_drop_location_constraint
        for completeness
        """
        # Write the dest location for apple mls
        self.out_apple_mls.location_dest_id = self.test_trailer_location_01
        #  Get locations to drop off apples
        values = {"location_dest_id": self.test_trailer_location_01.id}
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            self.picking_type_goods_out.u_drop_location_constraint = drop_constraint
            locs = self.MoveLine.suggest_locations(picking=self.picking_out, values=values)
            self.assertEqual(locs, self.out_apple_locs)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            self.picking_type_goods_out.u_drop_location_constraint = drop_constraint
            locs = self.MoveLine.suggest_locations(picking=self.picking_out, values=values)
            self.assertEqual(locs, self.out_all_locs)

    def test08_suggest_locations_limit_results(self):
        """Get the suggest locations via self and limit the results"""
        # Set u_drop_location_constraint
        self.picking_type_pick.u_drop_location_constraint = "suggest_with_empty"
        self.assertEqual(self.pick_apple_mls.suggest_locations(), self.pick_all_locs)
        # Limit the results
        locs = self.pick_apple_mls.suggest_locations(limit=1)
        self.assertEqual(len(locs), 1)
        self.assertIn(locs, self.pick_all_locs)

    def test09_validate_location_dest_nothing_dropppable(self):
        """Check that we just return when nothing is droppable"""
        # Create a pick but do not assign
        picking = self.create_picking(
            self.picking_type_pick, products_info=[{"product": self.apple, "qty": 5}], confirm=True
        )
        apple_mls = picking.move_line_ids

        # Check that suggested locations is not done as nothing is droppable
        self.assertIsNone(apple_mls.validate_location_dest())
        with self.mock_suggested_locations_pick as mock_suggest_locs:
            apple_mls.validate_location_dest()
            mock_suggest_locs.assert_not_called()

        # Complete the moves
        picking.move_lines.quantity_done = 5
        picking.action_done()

        # Sanity check that suggest_locations is not called
        self.assertIsNone(apple_mls.validate_location_dest())
        with self.mock_suggested_locations_pick as mock_suggest_locs:
            apple_mls.validate_location_dest()
            mock_suggest_locs.assert_not_called()

    def test10_validate_location_dest_view(self):
        """Check that we just return when the drop location is a view"""
        # Check location is a view
        self.assertEqual(self.out_location.usage, "view")
        # Sanity check that suggested_locations is not called
        with self.mock_suggested_locations_pick as mock_suggest_locs:
            self.assertIsNone(self.pick_mls.validate_location_dest(locations=self.out_location))
            mock_suggest_locs.assert_not_called()

    def test11_validation_of_locations_no_policy(self):
        """Check validate locations returns if not policy is set"""
        # Create an internal picking, which has no policy
        internal_picking = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "qty": 5}],
            confirm=True,
            assign=True,
        )
        apple_mls = internal_picking.move_line_ids
        # Check that _get_policy_class is not called
        with patch.object(self.MoveLine.__class__, "_get_policy_class") as mock_get_policy_class:
            self.assertIsNone(apple_mls.validate_location_dest())
            mock_get_policy_class.assert_not_called()

    def test12_validation_of_locations_by_product_non_enforced(self):
        """Check the validation policy for suggest constraints for by product policy"""
        # Check suggested locations for each product are correct
        self.assertEqual(
            self.pick_apple_mls.suggest_locations(), self.pick_apple_locs,
        )
        self.assertEqual(self.pick_banana_mls.suggest_locations(), self.test_goodsout_location_02)
        # Set policy to suggest
        self.picking_type_pick.u_drop_location_constraint = "suggest"
        # Check that for suggest the checks aren't done and it is just returned
        with self.mock_suggested_locations_pick as mock_suggest_locs:
            self.assertIsNone(self.pick_mls.validate_location_dest())
            mock_suggest_locs.assert_not_called()

    def test13_validation_of_locations_by_product_enforced(self):
        """Check the validation policy for enforced with product policy"""
        # Check suggested locations for each product are correct
        self.assertEqual(
            self.pick_apple_mls.suggest_locations(), self.pick_apple_locs,
        )
        self.assertEqual(self.pick_banana_mls.suggest_locations(), self.test_goodsout_location_02)
        # Set all the mls to a single location -> to later throw an error
        self.pick_mls.location_dest_id = self.test_goodsout_location_01
        # Set policy to enforce
        # Note this must be done afterward as enforce stops a write to an invalid dest loc
        self.picking_type_pick.u_drop_location_constraint = "enforce"
        # Try to validate now
        with self.assertRaises(ValidationError) as e:
            self.pick_mls.validate_location_dest()
        self.assertEqual(
            e.exception.name, "Drop off location must be one of the suggested locations"
        )
        # Set the mls destination for bananas to be a valid one
        self.pick_banana_mls.location_dest_id = self.test_goodsout_location_02
        # Check that the suggested locations are now correct, and no validation error
        self.assertIsNone(self.pick_mls.validate_location_dest())

    def test14_create_mls_when_no_policy_set(self):
        """Check that a pick can be created without a suggested locations policy"""
        # Create picking
        pick = self.create_picking(
            self.picking_type_internal,
            products_info=[{"product": self.apple, "qty": 5}],
            confirm=True,
            assign=True,
        )
        # Check mls has correct product
        self.assertEqual(pick.move_line_ids.product_id, self.apple)

    def test15_check_write_preprocessing(self):
        """Check validate locations is called within write, but is only validated once"""
        # Set constraint to one that is checked => enforce_with_empty
        self.picking_type_goods_out.u_drop_location_constraint = "enforce_with_empty"

        # Check the validate function called from within write
        with self.mock_validate_location_dest as mock_validate:
            # Write the dest loc (valid)
            self.out_apple_mls.location_dest_id = self.test_trailer_location_01
            mock_validate.assert_called_with(locations=self.test_trailer_location_01)

        # Check that suggest_locations gets called exactly once
        with self.mock_suggested_locations_out as mock_suggest_locs:
            self.out_apple_mls.location_dest_id = self.test_trailer_location_04
            mock_suggest_locs.assert_called_once()

    def test16_check_validate_skips(self):
        """Check that suggest locations is not called when:
        a) preprocessing is True and locations is None
        b) preprocessing is False and locations is not None
        """
        # Enforce checks
        self.picking_type_goods_out.u_drop_location_constraint = "enforce"

        # Check condition a
        with self.mock_suggested_locations_out as mock_suggest_locs:
            self.out_apple_mls.validate_location_dest()
            mock_suggest_locs.assert_not_called()

        # Check condition b
        with self.mock_suggested_locations_pick as mock_suggest_locs:
            self.pick_apple_mls.validate_location_dest(locations=self.test_goodsout_location_01)
            mock_suggest_locs.assert_not_called()

    def test17_allow_write_if_current_loc_view(self):
        """Do not try to validate a location if a current location is a view"""
        # Set constraint to enforce and check dest location is a view
        self.picking_type_goods_out.u_drop_location_constraint = "enforce"
        self.assertEqual(self.out_apple_mls.location_dest_id.usage, "view")
        # Check the suggest locations function is not called from within write
        with self.mock_suggested_locations_out as mock_suggest_locs:
            self.out_apple_mls.location_dest_id = self.test_trailer_location_04
            mock_suggest_locs.assert_not_called()
        # Check the dest location is correct and not a view
        self.assertEqual(self.out_apple_mls.location_dest_id, self.test_trailer_location_04)
        self.assertNotEqual(self.out_apple_mls.location_dest_id.usage, "view")
        # Now check that it is called when we try to write to the location
        with self.mock_suggested_locations_out as mock_suggest_locs:
            self.out_apple_mls.location_dest_id = self.test_trailer_location_04
            mock_suggest_locs.assert_called_with()

    def test18_set_invalid_dest_location(self):
        """Set an invalid destination location to begin with"""
        # Set constraint to enforce
        self.picking_type_pick.u_drop_location_constraint = "enforce"
        # Try to create a pick with an invalid destination location
        with self.assertRaises(ValidationError) as e:
            self.create_picking(
                self.picking_type_pick,
                products_info=[{"product": self.apple, "qty": 5}],
                confirm=True,
                assign=True,
                location_dest_id = self.test_goodsout_location_02.id
        )
        self.assertEqual(
            e.exception.name, "There are no valid locations to drop stock"
        )