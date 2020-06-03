# -*- coding: utf-8 -*-
from . import common
from ..models.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY
from odoo.exceptions import ValidationError


class TestStockMoveLine(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockMoveLine, cls).setUpClass()
        # Set policies
        cls.picking_type_pick.u_suggest_locations_policy = "by_product"
        cls.picking_type_goods_out.u_suggest_locations_policy = "match_move_line"
        cls.ByProduct = SUGGEST_LOCATION_REGISTRY["by_product"](cls.env, False)
        cls.ByMLS = SUGGEST_LOCATION_REGISTRY["match_move_line"](cls.env, False)
        cls.MoveLine = cls.env["stock.move.line"]
        # Create quants for picking and suggested location
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 10)
        cls.create_quant(cls.apple.id, cls.test_goodsout_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_goodsout_location_02.id, 10)
        cls.create_quant(cls.apple.id, cls.test_goodsout_location_03.id, 10)
        # Create picking
        cls._pick_info = [{"product": cls.banana, "qty": 5}, {"product": cls.apple, "qty": 5}]
        cls.picking = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True, assign=True
        )
        cls.mls = cls.picking.move_line_ids

    def test01_check_correct_picking_type(self):
        """ Check the pick types have the correct policy """
        # Check policy name
        self.assertEqual(self.picking_type_pick.u_suggest_locations_policy, "by_product")
        self.assertEqual(self.picking_type_goods_out.u_suggest_locations_policy, "match_move_line")

    def test02_get_policy_class(self):
        """ Check policy class returns the correct class """
        self.assertEqual(
            self.MoveLine._get_policy_class(self.picking_type_pick).name(), "by_product"
        )
        self.assertEqual(
            self.MoveLine._get_policy_class(self.picking_type_goods_out).name(), "match_move_line"
        )
        # Check error raised when no policy found
        with self.assertRaises(ValueError) as e:
            self.MoveLine._get_policy_class(self.picking_type_internal)
        self.assertEqual(
            str(e.exception),
            f"Policy with name={self.picking_type_internal.u_suggest_locations_policy} could not be found",
        )

    def test03_suggest_locations_errors_with_not_enough_info(self):
        """ Suggest locations by picking type should throw error when not enough information is
            given.
        """
        #  Error as no values given
        with self.assertRaises(ValueError) as e:
            self.MoveLine.suggest_locations()
        self.assertEqual(
            str(e.exception),
            "Missing information! If suggest locations is not done via self, picking_type "
            + "and values must be provided!",
        )
        # Error as only picking_type given
        with self.assertRaises(ValueError) as e:
            self.MoveLine.suggest_locations(picking_type=self.picking_type_pick)
        self.assertEqual(
            str(e.exception),
            "Missing information! If suggest locations is not done via self, picking_type "
            + "and values must be provided!",
        )
        #  Error as only values given
        values = {"product_id": self.apple.id, "picking_id": self.picking.id}
        with self.assertRaises(ValueError) as e:
            self.MoveLine.suggest_locations(values=values)
        self.assertEqual(
            str(e.exception),
            "Missing information! If suggest locations is not done via self, picking_type "
            + "and values must be provided!",
        )

    def test04_suggest_locations_errors_with_no_location_policy(self):
        """ Suggest locations by picking type should throw an error when the locations policy is 
            not set.
        """
        #  Get apple mls
        apple_mls = self.mls.filtered(lambda ml: ml.product_id == self.apple)
        #  Error as no location policy set
        with self.assertRaises(ValueError) as e:
            # Set policy to None
            self.picking_type_pick.u_suggest_locations_policy = None
            apple_mls.suggest_locations()
        self.assertEqual(str(e.exception), "No policy set")

    def test05_suggest_locations_via_self(self):
        """ Get the suggest locations via self
            This is set up for 'by_product' policy.
            We loop through all policies in a very simple way
         """
        #  Get apple mls
        apple_mls = self.mls.filtered(lambda ml: ml.product_id == self.apple)
        #  Get locations to drop off apples
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = apple_mls.suggest_locations()
            self.assertEqual(locs, self.test_goodsout_location_01 | self.test_goodsout_location_03)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = apple_mls.suggest_locations()
            self.assertEqual(
                locs,
                self.test_goodsout_location_01
                | self.test_goodsout_location_03
                | self.test_goodsout_location_04,
            )

    def test06_suggest_locations_via_picking_type_and_values(self):
        """ Get the suggest locations by picking type and values, not self
            This is set up for 'by_product' policy.
            We loop through all policies in a very simple way
         """
        #  Get locations to drop off apples
        values = {"product_id": self.apple.id, "picking_id": self.picking.id}
        for drop_constraint in ("dont_scan", "scan", "suggest", "enforce"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = self.MoveLine.suggest_locations(
                picking_type=self.picking_type_pick, values=values
            )
            self.assertEqual(locs, self.test_goodsout_location_01 | self.test_goodsout_location_03)
        # Add u_drop_location_constraint with empty
        for drop_constraint in ("suggest_with_empty", "enforce_with_empty"):
            self.picking_type_pick.u_drop_location_constraint = drop_constraint
            locs = self.MoveLine.suggest_locations(
                picking_type=self.picking_type_pick, values=values
            )
            self.assertEqual(
                locs,
                self.test_goodsout_location_01
                | self.test_goodsout_location_03
                | self.test_goodsout_location_04,
            )

    def test07_suggest_locations_limit_results(self):
        """ Get the suggest locations via self and limit the results.
            This is set up for 'by_product' policy.
            We loop through all policies in a very simple way
         """
        #  Get apple mls
        apple_mls = self.mls.filtered(lambda ml: ml.product_id == self.apple)
        # Set u_drop_location_constraint
        self.picking_type_pick.u_drop_location_constraint = "suggest_with_empty"
        self.assertEqual(
            apple_mls.suggest_locations(),
            self.test_goodsout_location_01
            | self.test_goodsout_location_03
            | self.test_goodsout_location_04,
        )
        # Limit the results
        locs = apple_mls.suggest_locations(limit=1)
        self.assertEqual(len(locs), 1)
        self.assertIn(
            locs,
            self.test_goodsout_location_01
            or self.test_goodsout_location_03
            or self.test_goodsout_location_04,
        )

    def test08_validate_location_dest_nothing_dropppable(self):
        """ Check that we just return when nothing is droppable """
        # Complete the moves
        self.picking.move_lines.quantity_done = 5
        self.picking.action_done()
        #  Get apple mls
        apple_mls = self.mls.filtered(lambda ml: ml.product_id == self.apple)
        self.assertIsNone(apple_mls.validate_location_dest())

    def test09_validate_location_dest_nothing_dropppable(self):
        """ Check that we just return when the drop location is a view """
        # Set locations to a view location
        self.out_location.write({"usage": "view"})
        locations = self.out_location
        self.assertIsNone(self.mls.validate_location_dest(locations))

    def test10_check_validate_on_write(self):
        """ Check the validation policy controls whether a write can be performed 
            for the location destination. 
        """
        # Set policy to suggest
        self.picking_type_pick.u_drop_location_constraint = "suggest"
        self.mls.write({"location_dest_id": self.test_goodsout_location_01})
        self.assertEqual(self.mls.location_dest_id, self.test_goodsout_location_01)
        # Set policy to enforce
        self.picking_type_pick.u_drop_location_constraint = "enforce"
        with self.assertRaises(ValidationError) as e:
            self.mls.write({"location_dest_id": self.test_goodsout_location_02})
        self.assertEqual(
            e.exception.name, "Drop off location must be one of the suggested locations"
        )
        self.assertEqual(self.mls.location_dest_id, self.test_goodsout_location_01)

    def test11_validation_of_locations_by_product(self):
        """ Check the validation policy for enforced and non enforced drop constraints for 
            by product policy. 
            Note: Cannot do a write on a destination location if enforce is true, and that
            location is not valid. 
        """
        #  Get different mls
        apple_mls = self.mls.filtered(lambda ml: ml.product_id == self.apple)
        banana_mls = self.mls.filtered(lambda ml: ml.product_id == self.banana)
        # Check suggested locations for each product are correct
        self.assertEqual(
            apple_mls.suggest_locations(),
            self.test_goodsout_location_01 | self.test_goodsout_location_03,
        )
        self.assertEqual(banana_mls.suggest_locations(), self.test_goodsout_location_02)
        # Set policy to suggest
        self.picking_type_pick.u_drop_location_constraint = "suggest"
        # Check that for suggest the checks aren't done and it is just returned
        self.assertIsNone(self.mls.validate_location_dest())
        # Set the mls destination to a suggested location for all mls
        # expect to fail, as banana should go to test_goodsout_location_02
        self.mls.write({"location_dest_id": self.test_goodsout_location_01})
        # Set policy to enforce
        # Note this must be done afterward as enforce stops a write to an invalid dest loc
        self.picking_type_pick.u_drop_location_constraint = "enforce"
        with self.assertRaises(ValidationError) as e:
            self.mls.validate_location_dest()
        self.assertEqual(
            e.exception.name, "Drop off location must be one of the suggested locations"
        )
        # Set the mls destination for bananas to be a valid one
        banana_mls.write({"location_dest_id": self.test_goodsout_location_02})
        # Check that the suggested locations are correct
        self.assertIsNone(self.mls.validate_location_dest())

    def test12_create_mls_when_no_policy_set(self):
        """ Check that a pick can be created without a suggested locations policy """
        self.picking_type_pick.u_suggest_locations_policy = None
        # Create quant and picking
        self.create_quant(self.fig.id, self.test_stock_location_03.id, 10)
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.fig, "qty": 5}],
            confirm=True,
            assign=True,
        )
        mls = pick.move_line_ids
        # No sugested locations
        self.assertEqual(mls.product_id, self.fig)
