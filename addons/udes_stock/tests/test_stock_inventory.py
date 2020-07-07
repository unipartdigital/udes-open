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
        """
        self.warehouse.u_inventory_adjust_reserved = True
        self.test_stock_inventory.action_start()
        self.test_stock_inventory.line_ids.product_qty -= 1

        self.test_stock_inventory.sudo(self.stock_user).action_done()
        self.assertEqual(self.test_stock_inventory.state, "done")

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
        self.test_stock_inventory.action_start()

    def test01_calculate_reserved_qty(self):
        """Test that reserved quantity is calculated correctly."""
        self.assertEqual(len(self.test_stock_inventory.line_ids), 1)

        self.assertEqual(self.test_stock_inventory.line_ids.reserved_qty, 1)

    def test02_calculate_reserved_qty_recalculate(self):
        """Test that reserved quantity can be correctly recalculated."""
        self.apple_quant.reserved_quantity = 2

        self.test_stock_inventory.line_ids._compute_reserved_qty()
        self.assertEqual(self.test_stock_inventory.line_ids.reserved_qty, 2)
