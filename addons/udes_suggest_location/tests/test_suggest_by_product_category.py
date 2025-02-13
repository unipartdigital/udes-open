from . import common
from ..registry.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY


class CommonSuggestByProductCategory(common.SuggestedLocations):

    @classmethod
    def setUpClass(cls):
        super(CommonSuggestByProductCategory, cls).setUpClass()
        cls.OrderPoint = cls.env["stock.warehouse.orderpoint"]
        cls.Location = cls.env["stock.location"]
        cls.PalletCategorisationCategory = cls.env.ref(
            "udes_stock.product_category_pallet_categorisation")
        cls.PalletCategorisationCategory.u_category_suggest_locations = True
        cls._setup_category_locations()
        cls._setup_categories()
        cls._setup_orderpoints()
        # Create quants
        cls.create_quant(cls.apple.id, cls.category_01_location01.id, 10)
        cls.create_quant(cls.apple.id, cls.category_01_location03.id, 10)
        cls.create_quant(cls.apple.id, cls.category_02_location02.id, 10)
        cls.create_quant(cls.apple.id, cls.category_03_location03.id, 10)
        cls.create_quant(cls.banana.id, cls.category_02_location01.id, 10)
        cls.create_quant(cls.banana.id, cls.category_01_location03.id, 10)
        cls.create_quant(cls.banana.id, cls.category_03_location02.id, 10)
        cls.create_quant(cls.cherry.id, cls.category_03_location01.id, 10)
        cls.create_quant(cls.cherry.id, cls.category_01_location04.id, 10)
        cls.create_quant(cls.cherry.id, cls.category_02_location04.id, 10)

        # Create picking
        cls._pick_info = [
            {"product": cls.banana, "qty": 5},
            {"product": cls.apple, "qty": 4},
            {"product": cls.cherry, "qty": 5}
        ]
        cls.picking = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True, assign=True
        )
        cls.mls = cls.picking.move_line_ids
        # Set different categories on products that will be used
        cls.apple.categ_id = cls.category_1.id
        cls.banana.categ_id = cls.category_2.id
        cls.cherry.categ_id = cls.category_3.id

    @classmethod
    def create_product_category(
            cls, category_name, parent_id=False, with_user=False, **kwargs
    ):
        ProductCategory = cls.env["product.category"]
        if with_user:
            ProductCategory = ProductCategory.with_user(with_user)
        vals = {
            "name": category_name,
            "parent_id": parent_id,
        }
        vals.update(kwargs)
        return ProductCategory.create(vals)

    @classmethod
    def _setup_category_locations(cls):
        cls.category_locations = (
            cls.create_location(
                f"View Location {i}", location_id=cls.stock_location.id, usage="view",
            ) for i in range(1, 4)
        )
        (
            cls.category_location_01,
            cls.category_location_02,
            cls.category_location_03,
        ) = cls.category_locations

        cls.category_01_locations = (
            cls.create_location(
                f"Category 01 Location {i}", location_id=cls.category_location_01.id,
            ) for i in range(1, 6)
        )

        (
            cls.category_01_location01,
            cls.category_01_location02,
            cls.category_01_location03,
            cls.category_01_location04,
            cls.category_01_location05,
        ) = cls.category_01_locations

        cls.category_02_locations = (
            cls.create_location(
                f"Category 02 Location {i}", location_id=cls.category_location_02.id,
            ) for i in range(1, 6)
        )

        (
            cls.category_02_location01,
            cls.category_02_location02,
            cls.category_02_location03,
            cls.category_02_location04,
            cls.category_02_location05,
        ) = cls.category_02_locations

        cls.category_03_locations = (
            cls.create_location(
                f"Category 03 Location {i}", location_id=cls.category_location_03.id,
            ) for i in range(1, 6)
        )

        (
            cls.category_03_location01,
            cls.category_03_location02,
            cls.category_03_location03,
            cls.category_03_location04,
            cls.category_03_location05,
        ) = cls.category_03_locations

    @classmethod
    def _setup_categories(cls):
        cls.category_1 = cls.create_product_category(
            category_name="Category 1",
            parent_id=cls.PalletCategorisationCategory.id,
            u_category_suggest_location_ids=[(6, 0, cls.category_location_01.ids)]
        )
        cls.category_2 = cls.create_product_category(
            category_name="Category 2",
            parent_id=cls.PalletCategorisationCategory.id,
            u_category_suggest_location_ids=[(6, 0, cls.category_location_02.ids)]
        )
        cls.category_2_3_locations = cls.category_location_03 | cls.category_location_02
        cls.category_3 = cls.create_product_category(
            category_name="Category 3",
            parent_id=cls.PalletCategorisationCategory.id,
            u_category_suggest_location_ids=[(6, 0, cls.category_2_3_locations.ids)]
        )

    @classmethod
    def _setup_orderpoints(cls):
        cls.orderpoint_1 = cls.OrderPoint.create({
            "product_id": cls.apple.id,
            "location_id": cls.category_01_location05.id,
            "product_min_qty": 5,
            "product_max_qty": 10,
        })

        cls.orderpoint_2 = cls.OrderPoint.create({
            "product_id": cls.banana.id,
            "location_id": cls.category_01_location02.id,
            "product_min_qty": 5,
            "product_max_qty": 10,
        })

        cls.orderpoint_3 = cls.OrderPoint.create({
            "product_id": cls.cherry.id,
            "location_id": cls.category_03_location05.id,
            "product_min_qty": 5,
            "product_max_qty": 10,
        })


class TestSuggestByProductCategory(CommonSuggestByProductCategory):

    @classmethod
    def setUpClass(cls):
        super(TestSuggestByProductCategory, cls).setUpClass()
        policy_name = "by_product_category"
        cls.ByProductCategory = SUGGEST_LOCATION_REGISTRY[policy_name](cls.env)
        # Set suggested locations policy to "by product category"
        cls.picking_type_pick.u_suggest_locations_policy = policy_name

    def test_check_correct_picking_type(self):
        """Check using the correct policy"""
        self.assertEqual(self.picking_type_pick.u_suggest_locations_policy, "by_product_category")

    def test_get_values_from_mls(self):
        """Get the product, location destination from move lines and suggested locations from product category"""
        apple_vals = self.ByProductCategory.get_values_from_mls(
            self.mls.filtered(lambda ml: ml.product_id == self.apple)
        )
        self.assertEqual(apple_vals.get("product"), self.apple)
        self.assertEqual(apple_vals.get("location"), self.check_location)
        self.assertEqual(apple_vals.get("location_ids"), self.category_location_01)

        banana_vals = self.ByProductCategory.get_values_from_mls(
            self.mls.filtered(lambda ml: ml.product_id == self.banana)
        )
        self.assertEqual(banana_vals.get("product"), self.banana)
        self.assertEqual(banana_vals.get("location"), self.check_location)
        self.assertEqual(banana_vals.get("location_ids"), self.category_location_02)

        cherry_vals = self.ByProductCategory.get_values_from_mls(
            self.mls.filtered(lambda ml: ml.product_id == self.cherry)
        )
        self.assertEqual(cherry_vals.get("product"), self.cherry)
        self.assertEqual(cherry_vals.get("location"), self.check_location)
        self.assertEqual(cherry_vals.get("location_ids"), self.category_2_3_locations)

    def test_get_values_from_mls_failure(self):
        """Fail to get details due to multiple move lines given"""
        with self.assertRaises(ValueError) as e:
            self.ByProductCategory.get_values_from_mls(self.mls)
        self.assertEqual(str(e.exception), f"Expected singleton: {self.mls.product_id}")

    def test_get_product_from_dict(self):
        """Check that the product is returned from the dictionary correctly"""
        #  Dictionary does not have product_id
        with self.assertRaises(ValueError) as e:
            self.ByProductCategory._get_product_from_dict({"product": self.apple.id})
        self.assertEqual(str(e.exception), "No product found")
        # Successful product found via integer
        prod = self.ByProductCategory._get_product_from_dict({"product_id": self.apple.id})
        self.assertEqual(len(prod), 1)
        self.assertEqual(prod, self.apple)

    def test_get_picking_from_dict(self):
        """Check that the picking is returned from the dictionary correctly"""
        #  Dictionary does not have picking_id
        with self.assertRaises(ValueError) as e:
            self.ByProductCategory._get_picking_from_dict({"picking": self.picking})
        self.assertEqual(str(e.exception), "No picking found")
        # Successful picking found via integer
        self.assertEqual(
            self.ByProductCategory._get_picking_from_dict({"picking_id": self.picking.id}), self.picking
        )

    def test_get_values_from_dict(self):
        """Check that get values returns the correct dict"""
        self.assertEqual(
            self.ByProductCategory.get_values_from_dict(
                {"product_id": self.apple.id, "picking_id": self.picking.id}
            ),
            {
                "product": self.apple,
                "location": self.picking.location_dest_id,
                "location_ids": self.apple.categ_id.u_suggest_location_ids,
            },
        )

    def test_get_locations(self):
        """Get locations based on product, location and category suggested locations"""
        apple_locs = self.ByProductCategory.get_locations(
            self.apple, self.stock_location, self.apple.categ_id.u_suggest_location_ids
        )
        self.assertEqual(len(apple_locs), 3)
        # Will show the order point location and 2 locations where there are quants.
        self.assertEqual(apple_locs, self.category_01_location01 | self.category_01_location03 | self.category_01_location05)

        banana_locs = self.ByProductCategory.get_locations(
            self.banana, self.stock_location, self.banana.categ_id.u_suggest_location_ids
        )
        # Will suggest only one location as category_01_location02 where banana has order point is
        # not child of category_02_location which is in suggested locations of category 2.
        self.assertEqual(len(banana_locs), 1)
        self.assertEqual(banana_locs, self.category_02_location01)

        chery_locs = self.ByProductCategory.get_locations(
            self.cherry, self.stock_location, self.cherry.categ_id.u_suggest_location_ids
        )
        self.assertEqual(len(chery_locs), 3)
        # Will show the order point location and 2 locations where there are quants for this product.
        self.assertEqual(chery_locs, self.category_03_location01 | self.category_02_location04 | self.category_03_location05)

        # Return no locations if no product in child locations
        self.assertEqual(len(self.ByProductCategory.get_locations(self.fig, self.stock_location, self.fig.categ_id.u_suggest_location_ids)), 0)

    def test_policy_empty_locations(self):
        """
        Testing that other products order point locations will be shown in suggest empty locations
        """
        policy_domain = self.ByProductCategory.get_policy_empty_location_domain(
            self.apple, self.stock_location, self.apple.categ_id.u_suggest_location_ids
        )
        policy_domain += [("barcode", "!=", False), ("quant_ids", "=", False)]
        empty_apple_locations = self.Location.search(policy_domain)
        self.assertIn(self.orderpoint_2.location_id, empty_apple_locations)


class TestSuggestByProductOrderpoint(CommonSuggestByProductCategory):
    @classmethod
    def setUpClass(cls):
        super(TestSuggestByProductOrderpoint, cls).setUpClass()
        policy_name = "by_product_category_orderpoint"
        cls.ByProductCategoryOrderpoint = SUGGEST_LOCATION_REGISTRY[policy_name](cls.env)
        # Set suggested locations policy to "by product category order point"
        cls.picking_type_pick.u_suggest_locations_policy = policy_name


    def test_policy_empty_locations(self):
        """Testing that other products order point locations will not be shown in suggest empty locations"""
        policy_domain = self.ByProductCategoryOrderpoint.get_policy_empty_location_domain(
            self.apple, self.stock_location, self.apple.categ_id.u_suggest_location_ids
        )
        policy_domain += [("barcode", "!=", False), ("quant_ids", "=", False)]
        empty_apple_locations = self.Location.search(policy_domain)
        self.assertNotIn(self.orderpoint_2.location_id, empty_apple_locations)
