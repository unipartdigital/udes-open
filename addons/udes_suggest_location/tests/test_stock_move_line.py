import unittest

from . import common
from ..registry.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY
from odoo.exceptions import ValidationError
from unittest.mock import patch


class TestStockMoveLine(common.SuggestedLocations):
    @classmethod
    def setUpClass(cls):
        super(TestStockMoveLine, cls).setUpClass()
        cls.MoveLine = cls.env["stock.move.line"]
        # Set policies, use by_product for pick
        cls.picking_type_pick.u_suggest_locations_policy = "by_product"
        cls.ByProduct = SUGGEST_LOCATION_REGISTRY["by_product"](cls.env)

        # Create quants for picking and suggested location
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 10)
        cls.create_quant(cls.apple.id, cls.test_check_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_check_location_02.id, 10)
        cls.create_quant(cls.apple.id, cls.test_check_location_03.id, 10)

        # Create picking
        cls._pick_info = [{"product": cls.banana, "qty": 5}, {"product": cls.apple, "qty": 5}]
        cls.picking_pick = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls._pick_info,
            confirm=True,
            assign=True,
        )
        cls.mls = cls.picking_pick.move_line_ids

        # Destination locations for each product
        cls.pick_apple_locs = cls.test_check_location_01 | cls.test_check_location_03
        pick_empty_locs = cls.test_check_location_04
        cls.pick_all_locs = cls.pick_apple_locs | pick_empty_locs

        # Particular movelines for pick
        cls.apple_mls = cls.mls.filtered(lambda ml: ml.product_id == cls.apple)
        cls.banana_mls = cls.mls.filtered(lambda ml: ml.product_id == cls.banana)

        # Mock functions, for suggest locations and validate
        # Suggest locations return empty locations
        cls.mock_suggested_locations = patch.object(
            cls.MoveLine.__class__,
            "suggest_locations",
            return_value=cls.test_check_location_04,
        )
        cls.mock_validate_location_dest = patch.object(
            cls.MoveLine.__class__, "validate_location_dest", return_value=None
        )

    def test_get_policy_class(self):
        """Check policy class returns the correct class"""
        # Fetch by product policy
        by_product = self.MoveLine._get_policy_class(self.picking_type_pick)
        # Check naming
        self.assertEqual(by_product.name(), "by_product")
        # Check error raised when no policy found
        self.picking_type_internal.u_suggest_locations_policy = False
        with self.assertRaises(ValueError) as e:
            self.MoveLine._get_policy_class(self.picking_type_internal)
        self.assertEqual(str(e.exception), f"Policy with name=False could not be found")

    def test_suggest_locations_errors_with_not_enough_info(self):
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

    def test_suggest_locations_errors_with_no_location_policy(self):
        """Suggest locations by picking type should throw an error when the locations policy is
        not set
        """
        #  Error as no location policy set
        with self.assertRaises(ValueError) as e:
            # Set policy to None
            self.picking_type_pick.u_suggest_locations_policy = None
            self.apple_mls.suggest_locations()
        self.assertEqual(str(e.exception), "No policy set")

    def test_suggest_locations_via_self_by_product(self):
        """Get the suggest locations via self for by product policy, looping through all
        drop location constraints for completeness
        """
        #  Get locations to drop off apples
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = self.apple_mls.suggest_locations()
            self.assertEqual(locs, self.pick_apple_locs)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = self.apple_mls.suggest_locations()
            self.assertEqual(locs, self.pick_all_locs)

    def test_suggest_locations_via_picking_and_values_by_product(self):
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

    def test_suggest_locations_limit_results(self):
        """Get the suggest locations via self and limit the results"""
        # Set u_drop_location_constraint
        self.picking_type_pick.u_drop_location_constraint = "suggest_with_empty"
        self.assertEqual(self.apple_mls.suggest_locations(), self.pick_all_locs)
        # Limit the results
        locs = self.apple_mls.suggest_locations(limit=1)
        self.assertEqual(len(locs), 1)
        self.assertIn(locs, self.pick_all_locs)

    def test_validate_location_dest_view(self):
        """Check that we just return when the drop location is a view"""
        # Check location is a view
        self.assertEqual(self.out_location.usage, "view")
        # Sanity check that suggested_locations is not called
        with self.mock_suggested_locations as mock_suggest_locs:
            self.assertIsNone(self.mls.validate_location_dest(locations=self.out_location))
            mock_suggest_locs.assert_not_called()

    def test_validation_of_locations_no_policy(self):
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

    def test_validation_of_locations_by_product_non_enforced(self):
        """Check the validation policy for suggest constraints for by product policy"""
        # Check suggested locations for each product are correct
        self.assertEqual(
            self.apple_mls.suggest_locations(),
            self.pick_apple_locs,
        )
        self.assertEqual(self.banana_mls.suggest_locations(), self.test_check_location_02)
        # Set policy to suggest
        self.picking_type_pick.u_drop_location_constraint = "suggest"
        # Check that for suggest the checks aren't done and it is just returned
        with self.mock_suggested_locations as mock_suggest_locs:
            self.assertIsNone(self.mls.validate_location_dest())
            mock_suggest_locs.assert_not_called()

    def test_validation_of_locations_by_product_enforced(self):
        """Check the validation policy for enforced with product policy"""
        # Check suggested locations for each product are correct
        self.assertEqual(
            self.apple_mls.suggest_locations(),
            self.pick_apple_locs,
        )
        self.assertEqual(self.banana_mls.suggest_locations(), self.test_check_location_02)
        # Set all the mls to a single location -> to later throw an error
        self.mls.location_dest_id = self.test_check_location_01
        # Set policy to enforce
        # Note this must be done afterward as enforce stops a write to an invalid dest loc
        self.picking_type_pick.u_drop_location_constraint = "enforce"
        # Try to validate now
        with self.assertRaises(ValidationError) as e:
            self.mls.validate_location_dest()
        self.assertEqual(
            e.exception.args[0], "Drop off location must be one of the suggested locations"
        )
        # Set the mls destination for bananas to be a valid one
        self.banana_mls.location_dest_id = self.test_check_location_02
        # Check that the suggested locations are now correct, and no validation error
        self.assertIsNone(self.mls.validate_location_dest())

    def test_create_mls_when_no_policy_set(self):
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

    def test_set_invalid_dest_location(self):
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
                location_dest_id=self.test_goodsout_location_02.id,
            )
        self.assertEqual(e.exception.args[0], "There are no valid locations to drop stock")


# TODO
# Reduce duplication
# - split generic tests into their own class
# - separate classes for policy-specific tests

class TestStockMoveLine2(common.SuggestedLocations):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.MoveLine = cls.env["stock.move.line"]
        # Set policies, use by_product for pick
        cls.picking_type_pick.u_suggest_locations_policy = "by_origin"
        cls.ByProduct = SUGGEST_LOCATION_REGISTRY["by_origin"](cls.env)

        # Create quants for picking and suggested location
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 10)
        cls.create_quant(cls.cherry.id, cls.test_stock_location_03.id, 10)
        cls.create_quant(cls.damson.id, cls.test_stock_location_04.id, 10)
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)

        # Create picking
        origin = 'SO0001'
        cls._pick_info1 = [{"product": cls.apple, "qty": 10}]
        cls._pick_info2 = [{"product": cls.banana, "qty": 10}, {"product": cls.cherry, "qty": 10}]
        cls._pick_info3 = [{"product": cls.damson, "qty": 10}]
        cls.picking1 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls._pick_info1,
            origin=origin,
            confirm=True,
            assign=True,
        )
        cls.picking2 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls._pick_info2,
            origin=origin,
            confirm=True,
            assign=True,
        )
        cls.picking3 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls._pick_info3,
            origin='SO0002',
            confirm=True,
            assign=True,
        )
        cls.mls = cls.picking1.move_line_ids | cls.picking2.move_line_ids | cls.picking3.move_line_ids

        # Complete pickings 1 & 3. Picking 2 should have Check 01 suggested, as
        # it shares an origin with Picking 1.
        for picking, location in zip((cls.picking1, cls.picking3), (cls.test_check_location_01, cls.test_check_location_02)):
            picking.move_line_ids.location_dest_id = location
            picking.move_line_ids.qty_done = picking.move_line_ids.product_uom_qty
            picking._action_done()

        # Destination locations for each product
        cls.pick_banana_locs = cls.test_check_location_01
        pick_empty_locs = cls.test_check_location_03 | cls.test_check_location_04
        cls.pick_all_locs = cls.pick_banana_locs | pick_empty_locs

        # Particular movelines for pick
        cls.apple_mls = cls.mls.filtered(lambda ml: ml.product_id == cls.apple)
        cls.banana_mls = cls.mls.filtered(lambda ml: ml.product_id == cls.banana)
        cls.cherry_mls = cls.mls.filtered(lambda ml: ml.product_id == cls.cherry)

##        # Mock functions, for suggest locations and validate
##        # Suggest locations return empty locations
##        cls.mock_suggested_locations = patch.object(
##            cls.MoveLine.__class__,
##            "suggest_locations",
##            return_value=cls.test_check_location_04,
##        )
##        cls.mock_validate_location_dest = patch.object(
##            cls.MoveLine.__class__, "validate_location_dest", return_value=None
##        )

    def test_get_policy_class(self):
        """Check policy class returns the correct class"""
        # Fetch by origin policy
        by_origin = self.MoveLine._get_policy_class(self.picking_type_pick)
        # Check naming
        self.assertEqual(by_origin.name(), "by_origin")

    def test_raises_error_if_policy_not_set(self):
        # Check error raised when no policy found
        self.picking_type_internal.u_suggest_locations_policy = False
        with self.assertRaises(ValueError) as e:
            self.MoveLine._get_policy_class(self.picking_type_internal)
        self.assertEqual(str(e.exception), "Policy with name=False could not be found")

    def test_suggest_locations_errors_with_not_enough_info(self):
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
            self.MoveLine.suggest_locations(picking=self.picking1)
        self.assertEqual(
            str(e.exception),
            "Missing information to suggest locations, please provide either move "
            + "lines or picking and values!",
        )
        #  Error as only values given
        values = {"product_id": self.banana.id, "picking": self.picking2.id}
        with self.assertRaises(ValueError) as e:
            self.MoveLine.suggest_locations(values=values)
        self.assertEqual(
            str(e.exception),
            "Missing information to suggest locations, please provide either move "
            + "lines or picking and values!",
        )

    def test_suggest_locations_errors_with_no_location_policy(self):
        """Suggest locations by picking type should throw an error when the locations policy is
        not set
        """
        #  Error as no location policy set
        with self.assertRaises(ValueError) as e:
            # Set policy to None
            self.picking_type_pick.u_suggest_locations_policy = None
            self.banana_mls.suggest_locations()
        self.assertEqual(str(e.exception), "No policy set")

    def test_suggest_locations_via_self_by_origin(self):
        """Get the suggest locations via self for by origin policy, looping through all
        drop location constraints for completeness
        """
        #  Get locations to drop off bananas
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            with self.subTest(drop_constraint=drop_constraint):
                self.picking_type_pick.u_drop_location_constraint = drop_constraint
                locs = self.banana_mls.suggest_locations()
                self.assertEqual(locs, self.pick_banana_locs)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            with self.subTest(drop_constraint=drop_constraint):
                self.picking_type_pick.u_drop_location_constraint = drop_constraint
                locs = self.banana_mls.suggest_locations()
                self.assertEqual(locs, self.pick_all_locs)

    def test_suggest_locations_via_picking_and_values_by_origin(self):
        """Get the suggest locations by picking and values, not self
        This is set up for 'by_origin' policy and loop through all u_drop_location_constraint
        for completeness
        """
        #  Get locations to drop off bananas
        values = {"product_id": self.banana.id, "picking_id": self.picking2.id}
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            with self.subTest(drop_constraint=drop_constraint):
                self.picking_type_pick.u_drop_location_constraint = drop_constraint
                locs = self.MoveLine.suggest_locations(picking=self.picking2, values=values)
                self.assertEqual(locs, self.pick_banana_locs)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            with self.subTest(drop_constraint=drop_constraint):
                self.picking_type_pick.u_drop_location_constraint = drop_constraint
                locs = self.MoveLine.suggest_locations(picking=self.picking2, values=values)
                self.assertEqual(locs, self.pick_all_locs)

    def test_suggest_locations_limit_results(self):
        """Get the suggest locations via self and limit the results"""
        # Set u_drop_location_constraint
        self.picking_type_pick.u_drop_location_constraint = "suggest_with_empty"
        self.assertEqual(self.banana_mls.suggest_locations(), self.pick_all_locs)
        # Limit the results
        locs = self.apple_mls.suggest_locations(limit=1)
        self.assertEqual(len(locs), 1)
        self.assertIn(locs, self.pick_all_locs)

    @unittest.skip('one at a time')
    def test_validate_location_dest_view(self):
        """Check that we just return when the drop location is a view"""
        # Check location is a view
        self.assertEqual(self.out_location.usage, "view")
        # Sanity check that suggested_locations is not called
        with self.mock_suggested_locations as mock_suggest_locs:
            self.assertIsNone(self.mls.validate_location_dest(locations=self.out_location))
            mock_suggest_locs.assert_not_called()

    @unittest.skip('one at a time')
    def test_validation_of_locations_no_policy(self):
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

    @unittest.skip('one at a time')
    def test_validation_of_locations_by_product_non_enforced(self):
        """Check the validation policy for suggest constraints for by product policy"""
        # Check suggested locations for each product are correct
        self.assertEqual(
            self.apple_mls.suggest_locations(),
            self.pick_apple_locs,
        )
        self.assertEqual(self.banana_mls.suggest_locations(), self.test_check_location_02)
        # Set policy to suggest
        self.picking_type_pick.u_drop_location_constraint = "suggest"
        # Check that for suggest the checks aren't done and it is just returned
        with self.mock_suggested_locations as mock_suggest_locs:
            self.assertIsNone(self.mls.validate_location_dest())
            mock_suggest_locs.assert_not_called()

    def test_validation_of_locations_by_product_enforced(self):
        """Check the validation policy for enforced with product policy"""
        # Check suggested locations for each product are correct
        self.assertEqual(
            self.banana_mls.suggest_locations(),
            self.pick_banana_locs,
        )
        self.assertEqual(self.cherry_mls.suggest_locations(), self.test_check_location_01)
        # Set all the mls to a single location -> to later throw an error
        self.picking2.move_line_ids.write({'location_dest_id': self.test_check_location_02.id})
        # Set policy to enforce
        # Note this must be done afterward as enforce stops a write to an invalid dest loc
        self.picking_type_pick.u_drop_location_constraint = "enforce"
        # Try to validate now
        with self.assertRaises(ValidationError) as e:
            self.mls.validate_location_dest()
        self.assertEqual(
            e.exception.args[0], "Drop off location must be one of the suggested locations"
        )
        # Set the mls destination to be a valid one
        self.picking2.move_line_ids.write({'location_dest_id': self.test_check_location_01.id})
        # Check that the suggested locations are now correct, and no validation error
        self.assertIsNone(self.mls.validate_location_dest())

    def test_create_mls_when_no_policy_set(self):
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

    def test_set_invalid_dest_location(self):
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
                location_dest_id=self.test_goodsout_location_02.id,
            )
        self.assertEqual(e.exception.args[0], "There are no valid locations to drop stock")
