# -*- coding: utf-8 -*-
from . import common
from ..models.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY


class TestSuggestByProduct(common.SuggestedLocations):
    @classmethod
    def setUpClass(cls):
        super(TestSuggestByProduct, cls).setUpClass()
        policy_name = "by_product"
        cls.ByProduct = SUGGEST_LOCATION_REGISTRY[policy_name](cls.env)
        # Set suggested locations policy to "by product"
        cls.picking_type_pick.u_suggest_locations_policy = policy_name
        # Create quants
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)
        cls.create_quant(cls.apple.id, cls.test_stock_location_02.id, 10)
        cls.create_quant(cls.banana.id, cls.test_stock_location_03.id, 10)
        # Create picking
        cls._pick_info = [{"product": cls.banana, "qty": 5}, {"product": cls.apple, "qty": 4}]
        cls.picking = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True, assign=True
        )
        cls.mls = cls.picking.move_line_ids

    def test00_check_correct_picking_type(self):
        """Check using the correct policy"""
        self.assertEqual(self.picking_type_pick.u_suggest_locations_policy, "by_product")

    def test01_get_values_from_mls(self):
        """Get the product and location destination from move lines"""
        vals = self.ByProduct.get_values_from_mls(
            self.mls.filtered(lambda ml: ml.product_id == self.apple)
        )
        self.assertEqual(vals.get("product"), self.apple)
        self.assertEqual(vals.get("location"), self.out_location)

    def test02_get_values_from_mls_failure(self):
        """Fail to get details due to multiple move lines given"""
        with self.assertRaises(ValueError) as e:
            self.ByProduct.get_values_from_mls(self.mls)
        self.assertEqual(str(e.exception), f"Expected singleton: {self.mls.product_id}")

    def test03_get_product_from_dict(self):
        """Check that the product is returned from the dictionary correctly"""
        #  Dictionary does not have product_id
        with self.assertRaises(ValueError) as e:
            self.ByProduct._get_product_from_dict({"product": self.apple.id})
        self.assertEqual(str(e.exception), "No product found")
        # Successful product found via integer
        prod = self.ByProduct._get_product_from_dict({"product_id": self.apple.id})
        self.assertEqual(len(prod), 1)
        self.assertEqual(prod, self.apple)

    def test04_get_picking_from_dict(self):
        """Check that the picking is returned from the dictionary correctly"""
        #  Dictionary does not have picking_id
        with self.assertRaises(ValueError) as e:
            self.ByProduct._get_picking_from_dict({"picking": self.picking})
        self.assertEqual(str(e.exception), "No picking found")
        # Successful picking found via integer
        self.assertEqual(
            self.ByProduct._get_picking_from_dict({"picking_id": self.picking.id}), self.picking
        )

    def test05_get_values_from_dict(self):
        """Check that get values returns the correct dict"""
        self.assertEqual(
            self.ByProduct.get_values_from_dict(
                {"product_id": self.apple.id, "picking_id": self.picking.id}
            ),
            {
                "product": self.apple,
                "location": self.picking.location_dest_id,
            },
        )

    def test06_get_locations(self):
        """Get locations based on product and location"""
        # Get locations based on product and location
        locs = self.ByProduct.get_locations(self.apple, self.stock_location)
        self.assertEqual(len(locs), 2)
        self.assertEqual(locs, self.test_stock_location_01 | self.test_stock_location_02)
        # Return no locations if no product in child locations
        self.assertEqual(len(self.ByProduct.get_locations(self.fig, self.stock_location)), 0)
