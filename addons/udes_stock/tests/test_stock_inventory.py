from odoo.exceptions import ValidationError
from . import common


class TestStockInventory(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        """Add a quant in a location to the setUpClass method."""
        super(TestStockInventory, cls).setUpClass()
        cls.apple_quant = cls.create_quant(cls.apple.id, cls.test_location_01.id, 5)

    def setUp(self):
        """Setup data for stock inventory adjustment."""
        self.User = self.env['res.users']

        super(TestStockInventory, self).setUp()
        self.warehouse = self.User.get_user_warehouse()
        self.warehouse.u_inventory_adjust_reserved = False
        self.apple_quant.reserved_quantity = 1.0
        self.test_stock_inventory = self.create_stock_inventory(name="Test Stock Check")

    def test01_reserved_correct_qty_allowed(self):
        """Test that inventory adjustments are allowed for reserved quants with
        u_inventory_adjust_reserved = False if the correct quantity is counted.
        """
        self.test_stock_inventory.action_start()
        self.assertEqual(len(self.test_stock_inventory.line_ids), 1)

        self.test_stock_inventory.sudo(self.stock_user).action_done()
        self.assertEqual(self.test_stock_inventory.state, "done")

    def test02_reserved_lower_qty_not_allowed(self):
        """Test that inventory adjustments are not allowed for reserved quants with
        u_inventory_adjust_reserved = False if a lower quantity is counted.
        """
        self.test_stock_inventory.action_start()
        self.test_stock_inventory.line_ids.product_qty -= 1

        with self.assertRaises(ValidationError) as e:
            self.test_stock_inventory.sudo(self.stock_user).action_done()
        self.assertEqual(
            e.exception.name,
            (
                "You are not allowed to adjust reserved stock. "
                "The stock has not been adjusted."
            )
        )

    def test03_reserved_higher_qty_not_allowed(self):
        """Test that inventory adjustments are not allowed for reserved quants with
        u_inventory_adjust_reserved = False if a higher quantity is counted.
        """
        self.test_stock_inventory.action_start()
        self.test_stock_inventory.line_ids.product_qty += 1

        with self.assertRaises(ValidationError) as e:
            self.test_stock_inventory.sudo(self.stock_user).action_done()
        self.assertEqual(
            e.exception.name,
            (
                "You are not allowed to adjust reserved stock. "
                "The stock has not been adjusted."
            )
        )

    def test04_reserved_wrong_qty_allowed_with_setting(self):
        """Test that inventory adjustments are allowed for reserved quants with
        u_inventory_adjust_reserved = True if a lower quantity is counted.

        There was a bug in odoo core that was updating move lines incorrectly, so
        we extend this test to also check move lines.
        """
        Picking = self.env['stock.picking']

        self.apple_quant.reserved_quantity = 0
        self.apple_quant.quantity = 20
        self.warehouse.u_inventory_adjust_reserved = True

        # Create four pickings with quantity 5
        products = [{'product': self.apple, 'qty': 5}]
        pickings = Picking.browse()
        for i in range(0, 4):
            pickings |= self.create_picking(self.picking_type_pick,
                                            products_info=products,
                                            confirm=True,
                                            assign=True)
        # We should have four move lines of quantity 5
        self.assertEqual(pickings.mapped('move_line_ids.product_uom_qty'),
                         [5, 5, 5, 5])
        # Apple quant is now fully reserved
        self.assertEqual(self.apple_quant.reserved_quantity, 20)

        # Start and validate inventory adjustment to 19
        self.test_stock_inventory.action_start()
        self.test_stock_inventory.line_ids.product_qty -= 1

        self.test_stock_inventory.sudo(self.stock_user).action_done()
        self.assertEqual(self.test_stock_inventory.state, "done")

        # We should have three move lines of quantity 5 and one of 4
        self.assertEqual(sorted(pickings.mapped('move_line_ids.product_uom_qty')),
                         sorted([4, 5, 5, 5]))
        # Apple quant has now quantity 19 and still fully reserved
        self.assertEqual(self.apple_quant.quantity, 19)
        self.assertEqual(self.apple_quant.reserved_quantity, 19)

    def test05_reserved_wrong_qty_allowed_by_debug_user(self):
        """Test that inventory adjustments are allowed for reserved quants with
        u_inventory_adjust_reserved = False if a lower quantity is counted
        by users in the debug group.
        """
        # Add stock user to debug group
        debug_group = self.env.ref('udes_security.group_debug_user')
        debug_group.write({'users': [(4, self.stock_user.id)]})

        self.test_stock_inventory.action_start()
        self.test_stock_inventory.line_ids.product_qty -= 1

        self.test_stock_inventory.sudo(self.stock_user).action_done()
        self.assertEqual(self.test_stock_inventory.state, "done")

    def test06_theoretical_quantity_changes(self):
        """Test that the system correctly identifies when the theoretical
        quantity is different than expected.
        """
        self.apple_quant.reserved_quantity = 0
        self.test_stock_inventory.action_start()

        self.assertFalse(
            self.test_stock_inventory._has_theoretical_quantity_changed(),
            "No changes to the theoretical quantity should have been detected"
        )

        self.apple_quant.quantity += 1
        self.assertTrue(
            self.test_stock_inventory._has_theoretical_quantity_changed(),
            "A change to the theoretical quantity should have been detected"
        )


class TestStockInventoryLine(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        """Add a quant in a location to the setUpClass method."""
        super(TestStockInventoryLine, cls).setUpClass()
        cls.apple_quant = cls.create_quant(cls.apple.id, cls.test_location_01.id, 5)

    def setUp(self):
        """Setup data to create stock inventory adjustment line."""
        super(TestStockInventoryLine, self).setUp()
        self.apple_quant.reserved_quantity = 1.0
        self.test_stock_inventory = self.create_stock_inventory(name="Test Stock Check")

    def test01_calculate_reserved_qty(self):
        """Test that reserved quantity is calculated correctly."""
        self.test_stock_inventory.action_start()

        self.assertEqual(len(self.test_stock_inventory.line_ids), 1)

        self.assertEqual(self.test_stock_inventory.line_ids.reserved_qty, 1)

    def test02_calculate_reserved_qty_recalculate(self):
        """Test that reserved quantity can be correctly recalculated."""
        self.test_stock_inventory.action_start()

        self.apple_quant.reserved_quantity = 2

        self.test_stock_inventory.line_ids._compute_reserved_qty()
        self.assertEqual(self.test_stock_inventory.line_ids.reserved_qty, 2)

    def test03_assert_same_key_quants_merged(self):
        """
        Assert that quants with the same key (product, location, package, lot, partner)
        are rolled into one Inventory Line, with the quantity of each quant summed
        """
        # Duplicate apple quant to double apple quantity
        self.apple_quant.copy()

        self.test_stock_inventory.action_start()

        # Assert that both apple quants were merged into one inventory line
        inventory_line = self.test_stock_inventory.line_ids[0]
        self.assertEqual(
            len(inventory_line), 1, f"{self.apple} quants should have been merged into one line"
        )

        expected_qty = sum(self.apple.stock_quant_ids.mapped("quantity"))
        qty_fields = ["product_qty", "theoretical_qty"]

        # Assert that quantity and theoretical quantity fields on inventory line
        # match summed total of apple quants
        for field in qty_fields:
            field_qty = inventory_line[field]
            self.assertEqual(
                field_qty, expected_qty, f"Line {field} should be {expected_qty}, got {field_qty}"
            )

    def test04_assert_parent_package_retained(self):
        """
        Assert that parent package is retained on the quant after updating product quantity on
        inventory line
        """
        # Create pallet with a package and assign package to apple quant
        pallet = self.create_package()
        package = self.create_package(package_id=pallet.id)
        self.apple_quant.package_id = package.id

        self.test_stock_inventory.action_start()

        # Set new quantity on inventory line
        inventory_line = self.test_stock_inventory.line_ids[0]
        old_qty = inventory_line.product_qty
        new_qty = old_qty + 1
        inventory_line.product_qty = new_qty

        # Validate inventory adjustment and assert that quantity was updated
        # and parent package retained for package
        self.test_stock_inventory.action_done()

        self.assertEqual(
            self.apple_quant.quantity,
            new_qty,
            f"{self.apple.name} quant qty should be {new_qty}, got: {self.apple_quant.quantity}",
        )

        self.assertEqual(
            package.package_id,
            pallet,
            f"{package} parent package should be {pallet}, got: {package.package_id}",
        )

    def test05_assert_parent_package_updated(self):
        """
        Assert that parent package is updated on the quant after being updated on inventory line
        """
        # Create package and assign it to apple quant
        package = self.create_package()
        self.apple_quant.package_id = package.id

        self.test_stock_inventory.action_start()

        # Create pallet and set it as new parent package on inventory line
        pallet = self.create_package()
        inventory_line = self.test_stock_inventory.line_ids[0]
        inventory_line.u_result_parent_package_id = pallet

        # Validate inventory adjustment and assert that parent package was updated
        self.test_stock_inventory.action_done()

        self.assertEqual(
            package.package_id,
            pallet,
            f"{package} parent package should be {pallet}, got: {package.package_id}",
        )


class TestStockInventoryFilters(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        """Setup products and create a Inventory Adjustment record"""
        super(TestStockInventoryFilters, cls).setUpClass()

        cls._setup_product_categories()
        cls._setup_products_in_categories()

        cls.test_stock_inventory = cls.create_stock_inventory(
            name="Test Stock Check", location_id=cls.test_location_01.id
        )

    @classmethod
    def create_product_category(cls, name, parent_category=None, **kwargs):
        """Create and return a Product Category record"""
        ProductCategory = cls.env["product.category"]

        vals = {"name": name, "parent_id": parent_category.id if parent_category else False}
        vals.update(kwargs)
        return ProductCategory.create(vals)

    @classmethod
    def create_product_in_category(cls, name, product_category, **kwargs):
        """Create and return a Product record in the supplied category"""
        kwargs["categ_id"] = product_category.id
        return cls.create_product(name, **kwargs)

    @classmethod
    def _setup_product_categories(cls):
        """Create product categories for testing"""
        cls.category_a = cls.create_product_category("A")
        cls.category_b = cls.create_product_category("B")

    @classmethod
    def _setup_products_in_categories(cls):
        """Create products in test categories, with a quant created for each product"""
        cls.product_a_1 = cls.create_product_in_category("Product A1", cls.category_a)
        cls.product_a_2 = cls.create_product_in_category("Product A2", cls.category_a)
        cls.product_b_1 = cls.create_product_in_category("Product B1", cls.category_b)

        cls.a_products = cls.product_a_1 | cls.product_a_2
        cls.b_products = cls.product_b_1

        cls.product_qty = 5
        for product in cls.a_products | cls.b_products:
            package = cls.create_package()
            cls.create_quant(
                product.id, cls.test_location_01.id, cls.product_qty, package_id=package.id
            )

    def _assert_inventory_lines_have_products(self, inventory_lines, products, expected=True):
        """
        Assert that each supplied Product is/isn't present in the supplied Inventory Lines.

        Optionally set `expected` (default True) to specify whether the products should or shouldn't
        be in the Inventory Lines.
        """
        inventory_lines_products = inventory_lines.mapped("product_id")

        for product in products:
            if expected:
                self.assertIn(
                    product,
                    inventory_lines_products,
                    f"{product.name} should be in Inventory Lines",
                )
            else:
                self.assertNotIn(
                    product,
                    inventory_lines_products,
                    f"{product.name} should not be in Inventory Lines",
                )

    def _assert_line_counts_equal(self, expected_line_count, actual_line_count):
        """Assert that expected line count matches actual line count"""
        self.assertEqual(
            expected_line_count,
            actual_line_count,
            f"{expected_line_count} lines should have been created, got: {actual_line_count}",
        )

    def test_assert_no_filter(self):
        """
        Assert that Inventory Adjustment record with no filter set returns all products with
        quants within specified location
        """
        Quant = self.env["stock.quant"]

        # Create product with quant in Test Location 2
        test_loc_2_product = self.create_product("Test Loc 2 Product")
        package = self.create_package()
        self.create_quant(
            test_loc_2_product.id,
            self.test_location_02.id,
            self.product_qty,
            package_id=package.id,
        )

        # Set inventory adjustment filter to none and start inventory
        self.test_stock_inventory.filter = "none"
        self.test_stock_inventory.action_start()

        # Get products with quants that are inside Test Location 1
        test_loc_1_quants = Quant.search([("location_id", "child_of", self.test_location_01.id)])
        test_loc_1_products = test_loc_1_quants.mapped("product_id")

        # Assert that one line was created for each product in Test Location 1
        inventory_lines = self.test_stock_inventory.line_ids
        expected_line_count = len(test_loc_1_products)
        actual_line_count = len(inventory_lines)

        self._assert_line_counts_equal(expected_line_count, actual_line_count)

        # Assert that Test Loc 1 products are in the Inventory Lines, but not Test Loc 2 Products
        self._assert_inventory_lines_have_products(inventory_lines, test_loc_1_products)
        self._assert_inventory_lines_have_products(
            inventory_lines, test_loc_2_product, expected=False
        )

    def test_assert_product_category_filter(self):
        """
        Assert that product category filter only creates lines for products
        within specified category
        """
        # Set inventory adjustment product category to A and start inventory
        self.test_stock_inventory.filter = "category"
        self.test_stock_inventory.category_id = self.category_a
        self.test_stock_inventory.action_start()

        # Assert that one line was created for each product in Category A
        inventory_lines = self.test_stock_inventory.line_ids
        expected_line_count = self.category_a.product_count
        actual_line_count = len(inventory_lines)

        self._assert_line_counts_equal(expected_line_count, actual_line_count)

        # Assert that A products are in the Inventory Lines, but not B products
        self._assert_inventory_lines_have_products(inventory_lines, self.a_products)
        self._assert_inventory_lines_have_products(inventory_lines, self.b_products, expected=False)

    def test_assert_product_filter(self):
        """Assert that product filter only creates lines for specified product"""
        # Create additional quants for product A1
        new_quant_count = 2
        for _ in range(0, new_quant_count):
            package = self.create_package()
            self.create_quant(
                self.product_a_1.id,
                self.test_location_01.id,
                self.product_qty,
                package_id=package.id,
            )

        # Set inventory adjustment product to A1 and start inventory
        self.test_stock_inventory.filter = "product"
        self.test_stock_inventory.product_id = self.product_a_1
        self.test_stock_inventory.action_start()

        # Assert that one line was created for each product in Category A
        inventory_lines = self.test_stock_inventory.line_ids
        expected_line_count = len(self.product_a_1) + new_quant_count
        actual_line_count = len(inventory_lines)

        self._assert_line_counts_equal(expected_line_count, actual_line_count)

        # Assert that A1 product is in the Inventory Lines
        self._assert_inventory_lines_have_products(inventory_lines, self.product_a_1)

    def test_assert_lot_filter(self):
        """Assert that lot filter only creates lines for specified lot"""
        # Set A1 to be tracked by Lot
        self.product_a_1.tracking = "lot"

        # Create lot and set it against A1 quant
        product_a_1_quant = self.product_a_1.stock_quant_ids[0]
        a1_lot = self.create_lot(self.product_a_1.id, self.product_a_1.name)
        product_a_1_quant.lot_id = a1_lot

        # Set inventory adjustment lot to A1 lot and start inventory
        self.test_stock_inventory.filter = "lot"
        self.test_stock_inventory.lot_id = a1_lot
        self.test_stock_inventory.action_start()

        # Assert that one line was created for A1 lot
        inventory_lines = self.test_stock_inventory.line_ids
        expected_line_count = len(product_a_1_quant)
        actual_line_count = len(inventory_lines)

        self._assert_line_counts_equal(expected_line_count, actual_line_count)

        # Assert that A1 product is in the Inventory Lines
        self._assert_inventory_lines_have_products(inventory_lines, self.product_a_1)

        # Assert that A1 lot is in the Inventory Lines
        inventory_lines_lots = inventory_lines.mapped("prod_lot_id")
        self.assertEqual(
            inventory_lines_lots, a1_lot, f"Inventory Lines should only contain Lot {a1_lot.name}"
        )

    def test_assert_package_filter(self):
        """Assert that package filter only creates lines for specified package"""
        # Put product B1 quant into the same package as A1
        product_a_1_quant = self.product_a_1.stock_quant_ids[0]
        product_b_1_quant = self.product_b_1.stock_quant_ids[0]

        a1_package = product_a_1_quant.package_id
        a1_package.name = self.product_a_1.name
        product_b_1_quant.package_id = a1_package

        # Set inventory adjustment package to A1 package and start inventory
        self.test_stock_inventory.filter = "pack"
        self.test_stock_inventory.package_id = a1_package
        self.test_stock_inventory.action_start()

        # Assert that lines were created for product A1 and B1
        inventory_lines = self.test_stock_inventory.line_ids
        expected_line_count = len(product_a_1_quant | product_b_1_quant)
        actual_line_count = len(inventory_lines)

        self._assert_line_counts_equal(expected_line_count, actual_line_count)

        # Assert that A1 and B1 products are in the Inventory Lines
        self._assert_inventory_lines_have_products(
            inventory_lines, self.product_a_1 | self.product_b_1
        )

        # Assert that A1 package is in the Inventory Lines
        inventory_lines_packages = inventory_lines.mapped("package_id")
        self.assertEqual(
            inventory_lines_packages,
            a1_package,
            f"Inventory Lines should only contain Package {a1_package.name}",
        )
