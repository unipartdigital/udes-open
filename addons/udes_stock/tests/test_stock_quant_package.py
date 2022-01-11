# -*- coding: utf-8 -*-
from .common import BaseUDES


class TestStockQuantPackageModel(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockQuantPackageModel, cls).setUpClass()
        cls.Package = cls.env["stock.quant.package"]
        User = cls.env["res.users"]

        warehouse = User.get_user_warehouse()
        # package
        cls.test_package = cls.Package.get_or_create("1001", create=True)
        cls.apple_quant = cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 10, package_id=cls.test_package.id
        )
        cls.create_quant(
            cls.banana.id, cls.test_stock_location_01.id, 5, package_id=cls.test_package.id
        )
        cls.test_user = cls.create_user("test_user", "test_user_login")

    def test01_get_quantities_by_default_key(self):
        """Get the product quantities of the package grouped by the default key - product_id"""
        self.assertEqual(
            self.test_package.get_quantities_by_key(), {self.apple: 10, self.banana: 5}
        )

    def test02_get_product_quantities_by_custom_key(self):
        """Get the product quantities by product_id.name"""
        self.assertEqual(
            self.test_package.get_quantities_by_key(get_key=lambda q: q.product_id.name),
            {self.apple.name: 10, self.banana.name: 5},
        )

    def test03_has_same_content(self):
        """Test has same content of three packages, two are the same and one is not"""
        # Create two new packages with same content but different content than default package
        test_package_2 = self.Package.get_or_create("1002", create=True)
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_2.id
        )
        test_package_3 = self.Package.get_or_create("1003", create=True)
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_3.id
        )
        self.assertFalse(self.test_package.has_same_content(test_package_2))
        self.assertTrue(test_package_2.has_same_content(test_package_3))

    def test04_has_same_product_but_different_lots(self):
        """Test the default key checks the same products and quantities in two
        different packages but different lots.
        """
        apple_quant_info = {
            "product_id": self.apple.id,
            "location_id": self.test_stock_location_01.id,
            "qty": 5,
        }
        banana_quant_info = {
            "product_id": self.banana.id,
            "location_id": self.test_stock_location_01.id,
            "qty": 5,
        }
        # Create two new packages with two quants with lot each
        test_package_1 = self.Package.get_or_create("1001", create=True)
        self.create_quant(**apple_quant_info, package_id=test_package_1.id, lot_name="LOT001")
        self.create_quant(**banana_quant_info, package_id=test_package_1.id, lot_name="LOT001")
        test_package_2 = self.Package.get_or_create("1002", create=True)
        self.create_quant(**apple_quant_info, package_id=test_package_2.id, lot_name="LOT002")
        self.create_quant(**banana_quant_info, package_id=test_package_2.id, lot_name="LOT002")
        # Check they should have the same content by product
        self.assertTrue(test_package_1.has_same_content(test_package_2))
        # Check they should NOT have the same content by product and lot
        get_key = lambda p: (p.product_id, p.lot_id)
        self.assertFalse(test_package_1.has_same_content(test_package_2, get_key=get_key))

    def test05_has_same_content_multiple_packages(self):
        """Test the two groups of packages have the same content:
        Group 1: 15 apples (10 + 5)
        Group 2: 15 apples (5 + 5 + 5)
        """
        quant_info_10 = {
            "product_id": self.apple.id,
            "location_id": self.test_stock_location_01.id,
            "qty": 10,
        }
        quant_info_5 = {
            "product_id": self.apple.id,
            "location_id": self.test_stock_location_01.id,
            "qty": 5,
        }
        # Create new packages with 10, 5, 5, 5, 5 apples each
        test_package_1 = self.Package.get_or_create("2001", create=True)
        self.create_quant(**quant_info_10, package_id=test_package_1.id)
        test_package_2 = self.Package.get_or_create("2002", create=True)
        self.create_quant(**quant_info_5, package_id=test_package_2.id)
        test_package_3 = self.Package.get_or_create("2003", create=True)
        self.create_quant(**quant_info_5, package_id=test_package_3.id)
        test_package_4 = self.Package.get_or_create("2004", create=True)
        self.create_quant(**quant_info_5, package_id=test_package_4.id)
        test_package_5 = self.Package.get_or_create("2005", create=True)
        self.create_quant(**quant_info_5, package_id=test_package_5.id)
        # Split all packages in two groups
        group_1 = test_package_1 | test_package_2
        group_2 = test_package_3 | test_package_4 | test_package_5
        # Check they should have the same content by product
        self.assertTrue(group_1.has_same_content(group_2))

    def test06_get_reserved_quantity(self):
        """Get reserved quantity check"""
        self.assertEqual(self.test_package.get_reserved_quantity(), 0)
        self.apple_quant.reserved_quantity = 5
        self.assertEqual(self.test_package.get_reserved_quantity(), 5)
        # Add additional stuff to package
        self.create_quant(
            self.banana.id,
            self.test_stock_location_01.id,
            20,
            reserved_quantity=10,
            package_id=self.test_package.id,
        )
        self.assertEqual(self.test_package.get_reserved_quantity(), 15)

    def test07_find_move_lines_simple(self):
        """Find move lines of package"""
        # Create a picking from test package
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 12},
                {"product": self.banana, "uom_qty": 5},
            ],
            assign=True,
            confirm=True,
        )
        # Check get the move lines
        mls = self.test_package.find_move_lines()
        self.assertEqual(mls, pick.move_line_ids)

    def test08_find_move_lines_additional_domain(self):
        """Find move lines of package with additional domain"""
        # Create a picking from test package
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 12},
                {"product": self.banana, "uom_qty": 5},
            ],
            assign=True,
            confirm=True,
        )
        # Filter out move lines by an additional domain, and check it is the apple move line
        mls = self.test_package.find_move_lines(aux_domain=[("product_id", "=", self.apple.id)])
        self.assertEqual(mls, pick.move_line_ids.filtered(lambda ml: ml.product_id == self.apple))
        self.assertEqual(mls.product_id, self.apple)

    def test09_mls_can_fulfill_success_no_excess_multiple_move_lines(self):
        """Test to check if the move lines can be met by the package, then no excess given"""
        self.create_quant(self.apple.id, self.test_stock_location_02.id, 10)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 10)
        # Create a new pick
        product_info = [
            {"product": self.banana, "uom_qty": 2},
            {"product": self.apple, "uom_qty": 10},
        ]
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=product_info,
            assign=True,
            confirm=True,
            location_id=self.test_stock_location_02.id,
        )
        # Get mls
        mls = pick.move_line_ids
        can_fulfil_mls, excess_mls = self.test_package.mls_can_fulfil(mls)
        self.assertIn(self.banana, can_fulfil_mls.product_id)
        self.assertIn(self.apple, can_fulfil_mls.product_id)
        self.assertEqual(can_fulfil_mls.mapped("product_qty"), [10, 2])
        self.assertFalse(excess_mls, "Expected no excess move lines")

    def test10_mls_can_fulfill_success_with_excess_simple(self):
        """Test to check that when a move line has quantity > package quantity, it returns which
        it can meet, and the excess move line.
        """
        self.create_quant(self.apple.id, self.test_stock_location_02.id, 20)
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "uom_qty": 18}],
            assign=True,
            confirm=True,
            location_id=self.test_stock_location_02.id,
        )
        # Get apple mls
        mls = pick.move_line_ids
        self.assertEqual(mls.product_qty, 18)
        # Check move line can fulfill package and will split
        can_fulfil_mls, excess_mls = self.test_package.mls_can_fulfil(mls)
        self.assertEqual(len(can_fulfil_mls), 1)
        self.assertEqual(len(excess_mls), 1)
        self.assertEqual(can_fulfil_mls.product_qty, 10)
        self.assertEqual(excess_mls.product_qty, 8)

    def test11_mls_can_fulfill_success_with_excess_multiple_move_lines(self):
        """Test to check that when multiple move lines passed, it correctly splits those when
        the move lines quantity > package quantity, and meets those it can
        """
        # Create a fig quant in test_package, and quants for picking
        self.create_quant(
            self.fig.id, self.test_stock_location_01.id, 15, package_id=self.test_package.id
        )
        self.create_quant(self.apple.id, self.test_stock_location_02.id, 20)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 20)
        self.create_quant(self.fig.id, self.test_stock_location_02.id, 15)
        # Create pick
        product_info = [
            {"product": self.banana, "uom_qty": 17},
            {"product": self.fig, "uom_qty": 15},
            {"product": self.apple, "uom_qty": 18},
        ]
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=product_info,
            assign=True,
            confirm=True,
            location_id=self.test_stock_location_02.id,
        )
        # Get apple mls
        mls = pick.move_line_ids
        self.assertEqual(mls.mapped("product_qty"), [17, 15, 18])
        # Check move line can fulfill package and will split
        can_fulfil_mls, excess_mls = self.test_package.mls_can_fulfil(mls)
        self.assertEqual(len(can_fulfil_mls), 3)
        self.assertEqual(can_fulfil_mls.mapped("product_qty"), [10, 5, 15])
        self.assertIn(self.fig, can_fulfil_mls.product_id)
        self.assertIn(self.banana, can_fulfil_mls.product_id)
        self.assertIn(self.apple, can_fulfil_mls.product_id)
        # Two were split
        self.assertEqual(len(excess_mls), 2)
        self.assertNotIn(self.fig, excess_mls.product_id)
        self.assertIn(self.apple, excess_mls.product_id)
        self.assertIn(self.banana, excess_mls.product_id)
        self.assertEqual(excess_mls.mapped("product_qty"), [8, 12])


class TestCreatePicking(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestCreatePicking, cls).setUpClass()

        Package = cls.env["stock.quant.package"]

        cls.test_package = Package.get_or_create("1001", create=True)
        cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 10, package_id=cls.test_package.id
        )
        cls.create_quant(
            cls.banana.id, cls.test_stock_location_01.id, 5, package_id=cls.test_package.id
        )
        cls.test_user = cls.create_user("test_user", "test_user_login")

    def test01_single_package(self):
        """Create a picking from a single quant"""
        pick = self.test_package.create_picking(self.picking_type_goods_out)
        # Confirm made in state draft
        self.assertEqual(pick.state, "draft")
        # Confirm package location used if non specified
        self.assertEqual(pick.location_id, self.test_stock_location_01)
        # Confirm default dest location used if non specified
        self.assertEqual(pick.location_dest_id, self.trailer_location)
        # Confirm correct picking type id associated
        self.assertEqual(pick.picking_type_id, self.picking_type_goods_out)
        # Check default priority is 0 = 'Normal'
        self.assertEqual(pick.priority, "0")
        #  Check picking has correct quantities associated to it
        self.assertEqual(pick.move_lines.mapped("product_id"), (self.apple | self.banana))
        self.assertEqual(pick.move_lines.mapped("product_qty"), [10, 5])

    def test02_single_package_extra_kwargs(self):
        """Create a picking from a single package
        - confirm
        - priority
        - assign_user
        - non-default location_id
        - non-default location_dest_id
        """
        pick = self.test_package.create_picking(
            self.picking_type_goods_out,
            confirm=True,
            priority="1",
            user_id=self.test_user.id,
            location_id=self.test_received_location_01.id,
            location_dest_id=self.test_goodsout_location_02.id,
        )
        # Confirm in state assigned
        self.assertEqual(pick.state, "confirmed")
        # Check user is assigned
        self.assertEqual(pick.user_id, self.test_user)
        # Confirm default location used if non specified
        self.assertEqual(pick.location_id, self.test_received_location_01)
        # Confirm default dest location used if non specified
        self.assertEqual(pick.location_dest_id, self.test_goodsout_location_02)
        # Confirm correct picking type id associated
        self.assertEqual(pick.picking_type_id, self.picking_type_goods_out)
        # Check priority is 1 = 'Urgent'
        self.assertEqual(pick.priority, "1")
        #  Check picking has correct quantities associated to it
        self.assertEqual(pick.move_lines.mapped("product_id"), (self.apple | self.banana))
        self.assertEqual(pick.move_lines.mapped("product_qty"), [10, 5])

    def test03_single_package_correct_package(self):
        """Test that create_picking uses the right package when assigning
        the picking
        """
        Package = self.env["stock.quant.package"]

        # Create a bunch of packages with identical contents in the same
        # location
        packages = Package.browse()
        for i in range(5):
            package = Package.create({})
            self.create_quant(
                self.apple.id, self.test_stock_location_01.id, 10, package_id=package.id
            )
            packages |= package
        self.assertEqual(len(packages), 5)

        package = packages[2]
        pick = package.create_picking(self.picking_type_pick, confirm=True, assign=True)
        self.assertEqual(pick.state, "assigned")
        self.assertEqual(pick.move_line_ids.package_id, package)
