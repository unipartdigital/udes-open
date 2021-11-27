# -*- coding: utf-8 -*-
from . import common
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict


class TestStockMoveLine(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockMoveLine, cls).setUpClass()
        # Order the banana first to allow for sorting checks later on
        cls._pick_info = [{"product": cls.banana, "qty": 5}, {"product": cls.apple, "qty": 4}]
        cls.picking = cls.create_picking(
            cls.picking_type_goods_in, products_info=cls._pick_info, confirm=True, assign=True
        )
        cls.mls = cls.picking.move_line_ids
        cls.apple_move = cls.picking.move_lines.filtered(lambda m: m.product_id == cls.apple)
        cls.banana_move = cls.picking.move_lines.filtered(lambda m: m.product_id == cls.banana)
        cls.apple_move_line = cls.picking.move_line_ids.filtered(
            lambda m: m.product_id == cls.apple
        )
        cls.banana_move_line = cls.picking.move_line_ids.filtered(
            lambda m: m.product_id == cls.banana
        )

    def test01_get_quantities_by_key(self):
        """Get the quants related to the move lines"""
        # Set expected goods in picking info
        expected = {self.banana: 5, self.apple: 4}
        # Check it matches with the moves lines of the default goods in picking
        self.assertEqual(self.mls.get_quantities_by_key(), expected)

    def test02_get_quantities_by_key_multiple_products(self):
        """Get the quants related to the move lines for multiple products"""
        # Create three quants in stock locations and different packages
        test_package_1 = self.create_package()
        test_package_2 = self.create_package()
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            10,
            package_id=test_package_1.id,
        )
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_1.id
        )
        self.create_quant(
            self.apple.id,
            self.test_stock_location_02.id,
            10,
            package_id=test_package_2.id,
        )
        # Create pick to reserve the quants
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "qty": 12}, {"product": self.banana, "qty": 5}],
            assign=True,
            confirm=True,
        )
        lines = pick.move_line_ids
        # Set expected goods in picking info
        expected = {
            (self.banana, test_package_1): 5,
            (self.apple, test_package_1): 10,
            (self.apple, test_package_2): 2,
        }
        # Check it matches with the moves lines of the new pick
        get_key = lambda ml: (ml.product_id, ml.package_id)
        key_quantities = lines.get_quantities_by_key(get_key=get_key)
        for key, expected_quantity in expected.items():
            self.assertEqual(key_quantities[key], expected_quantity)

    def test03_sort_by_key(self):
        """Get the move lines sorted by location and product"""
        # Check the order is originally: banana and apple
        self.assertEqual(
            self.mls.product_id.mapped("name"), ["Test product Banana", "Test product Apple"]
        )
        # Check the products get sorted by product id (since both mls have the same source location)
        self.assertEqual(
            self.mls.sort_by_key().mapped("product_id.name"),
            ["Test product Apple", "Test product Banana"],
        )

    def test04_sort_by_key_custom(self):
        """Get the move lines sorted by product qty then product id"""
        pick_info = [
            {"product": self.banana, "qty": 5},
            {"product": self.fig, "qty": 4},
            {"product": self.apple, "qty": 5},
        ]
        # Create picking
        picking = self.create_picking(
            self.picking_type_goods_in, products_info=pick_info, confirm=True, assign=True
        )
        mls = picking.move_line_ids
        # Check the order is originally: banana, fig and apple
        self.assertEqual(
            mls.product_id.mapped("name"),
            ["Test product Banana", "Test product Fig", "Test product Apple"],
        )
        # Check the move lines get sorted by qty and then product id
        self.assertEqual(
            mls.sort_by_key(sort_key=lambda ml: (ml.product_qty, ml.product_id.id)).mapped(
                "product_id.name"
            ),
            ["Test product Fig", "Test product Apple", "Test product Banana"],
        )

    def test05_split_by_qty_success(self):
        """Test split of move lines by qty"""
        # Get apple move line from default goods in picking
        ml_apple = self.apple_move_line
        # Check the move line has the correct quantity and product
        self.assertEqual(ml_apple.product_qty, 4)
        self.assertEqual(ml_apple.product_id, self.apple)
        # Split line up by quantity = 1
        new_ml = ml_apple._split(1)
        # New move line should have quantity 1
        self.assertEqual(new_ml.product_id, self.apple)
        self.assertEqual(new_ml.product_qty, 1)
        # Original move line should have quantity 3
        self.assertEqual(ml_apple.product_qty, 3)

    def test06_split_by_qty_failure(self):
        """Try to split the move line by qty more than that is in there"""
        # Get apple move line from default goods in picking
        ml_apple = self.apple_move_line
        # Check the move line has the correct quantity and product
        self.assertEqual(ml_apple.product_qty, 4)
        self.assertEqual(ml_apple.product_id, self.apple)
        # Try to split line by quantity = 5, should just return ml_apple intact
        new_ml = ml_apple._split(5)
        self.assertEqual(new_ml, ml_apple)
        self.assertEqual(new_ml.product_qty, 4)
        self.assertEqual(new_ml.product_id, self.apple)

    def test07_split_by_done_simple(self):
        """Split the move line by qty done"""
        # Get apple move line from default goods in picking
        ml_apple = self.apple_move_line
        # Update the move to be partially done
        self.update_move(self.apple_move, 3)
        # Check the update is propagated to the move line
        self.assertEqual(ml_apple.product_qty, 4)
        self.assertEqual(ml_apple.qty_done, 3)
        # Split by done qty
        new_ml = ml_apple._split()
        # Check new ml
        self.assertEqual(new_ml.product_qty, 1)
        self.assertEqual(new_ml.qty_done, 0)
        # Check original ml
        self.assertEqual(ml_apple.product_qty, 3)
        self.assertEqual(ml_apple.qty_done, 3)

    def test08_split_by_qty_with_done_qty_success(self):
        """Split the move line by qty when some has already been done,
        but the quantity to split matches with remaining quantity to do."""
        # Get apple move line from default goods in picking
        ml_apple = self.apple_move_line
        # Update the move to be partially done
        self.update_move(self.apple_move, 3)
        # Check the update is propagated to the move line
        self.assertEqual(ml_apple.product_qty, 4)
        self.assertEqual(ml_apple.qty_done, 3)
        # Split the apple move line with qty one - expect to split at 3 = qty_done
        new_ml = ml_apple._split(1)
        # Check new ml
        self.assertEqual(new_ml.product_qty, 1)
        self.assertEqual(new_ml.qty_done, 0)
        # Check existing ml
        self.assertEqual(ml_apple.product_qty, 3)
        self.assertEqual(ml_apple.qty_done, 3)

    def test09_split_by_qty_with_done_qty_failure(self):
        """Split the move line by qty when some has already been done,
        but the quantity to split matches with remaining quantity to do."""
        # Get apple move line from default goods in picking
        ml_apple = self.apple_move_line
        # Update the move to be partially done
        self.update_move(self.apple_move, 3)
        # Check the update is propagated to the move line
        self.assertEqual(ml_apple.product_qty, 4)
        self.assertEqual(ml_apple.qty_done, 3)
        # Try to split the apple move line with qty two raises an error
        with self.assertRaises(ValidationError) as e:
            ml_apple._split(2)
        msg = "Trying to split a move line with quantity done at picking %s" % self.picking.name
        self.assertEqual(e.exception.name, msg)

    def test10_get_move_lines_done_and_done_and_incomplete(self):
        """Check the get_move_lines_done and get_move_lines_incomplete function works as expected"""
        # Check no done move lines
        self.assertEqual(len(self.mls.get_lines_done()), 0)
        self.assertEqual(len(self.mls.get_lines_incomplete()), 2)
        # Complete the apple move
        self.update_move(self.apple_move, 4)
        # Check that one move line is complete
        self.assertEqual(len(self.mls.get_lines_done()), 1)
        self.assertEqual(len(self.mls.get_lines_incomplete()), 1)
        # Complete partially the banana move
        self.update_move(self.banana_move, 1)
        # Check that one move line is complete still
        self.assertEqual(len(self.mls.get_lines_done()), 1)
        self.assertEqual(len(self.mls.get_lines_incomplete()), 1)
        # Complete the rest of the move line and over receive - update move is cumulative
        self.update_move(self.banana_move, 10)
        # Check all move lines are complete
        self.assertEqual(len(self.mls.get_lines_done()), 2)
        self.assertEqual(len(self.mls.get_lines_incomplete()), 0)

    def test11_get_quants(self):
        """Check get_quants returns what is expected"""
        # Create three quants in stock locations
        test_package_1 = self.create_package()
        test_package_2 = self.create_package()
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            10,
            package_id=test_package_1.id,
        )
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_1.id
        )
        self.create_quant(
            self.apple.id,
            self.test_stock_location_02.id,
            10,
            package_id=test_package_2.id,
        )
        # Create pick to reserve the quants
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "qty": 12}, {"product": self.banana, "qty": 8}],
            assign=True,
            confirm=True,
        )
        # Get quants
        quants = pick.move_line_ids.get_quants()
        # Check result of get_quants
        self.assertEqual(quants.product_id, (self.apple | self.banana))
        self.assertTrue(
            sum(quants.filtered(lambda q: q.product_id == self.apple).mapped("quantity")) == 20
        )
        self.assertTrue(
            sum(quants.filtered(lambda q: q.product_id == self.banana).mapped("quantity")) == 5
        )

    def test12_move_line_for_qty_simple(self):
        """Check move_lines_for_qty returns the move line if satisfied straightaway"""
        # Get apple move line from default goods in picking
        ml_apple = self.apple_move_line
        result, new_ml, quantity = ml_apple.move_lines_for_qty(4)
        self.assertEqual(result, ml_apple)
        self.assertEqual(result.product_qty, 4)
        self.assertIsNone(new_ml)
        self.assertEqual(quantity, 0)

    def test13_move_line_for_qty_split(self):
        """Test when a subset of move lines are to be returned, with one being split"""
        # Get banana move line from default goods in picking
        ml_banana = self.banana_move_line
        result, new_ml, quantity = ml_banana.move_lines_for_qty(1)
        # Check returned move line matches requested quantity
        self.assertEqual(result.product_id, self.banana, "Expected product was a banana")
        self.assertEqual(sum(result.mapped("product_qty")), 1, "Expected quantity to be one")
        self.assertEqual(new_ml.product_id, self.banana, "Expected product was a banana")
        self.assertEqual(new_ml.product_qty, 4, "Expected quantity of new ml was four")
        self.assertEqual(quantity, 0, "Expected the un-met quantity to be 0")

    def test14_move_line_for_qty_split_cannot_fulfil(self):
        """Test when a subset of move lines are to be returned, where the quantity > than that in mls"""
        # Get banana move line from default goods in picking
        ml_banana = self.banana_move_line
        result, new_ml, quantity = ml_banana.move_lines_for_qty(11)
        # Check returns move line, and remaining qty needed
        self.assertEqual(result.product_id, self.banana, "Expected product was a banana")
        self.assertEqual(sum(result.mapped("product_qty")), 5, "Expected quantity to be five")
        self.assertEqual(quantity, 6, "Expected the un-met quantity to be six")
        self.assertIsNone(new_ml)

    def test15_move_line_for_qty_partial_split_default_sorting(self):
        """Test when a subset of move lines are to be returned, with one being split, and one original one
        Uses the default sorting
        """
        # Create additional move lines in a new picking
        pick_info = [{"product": self.banana, "qty": 17}]
        new_picking = self.create_picking(
            self.picking_type_goods_in, products_info=pick_info, confirm=True, assign=True
        )
        mls_banana = self.banana_move_line | new_picking.move_line_ids
        result, new_ml, quantity = mls_banana.move_lines_for_qty(19)
        # Check returned move line matches requested quantity
        self.assertEqual(result.product_id, self.banana, "Expected product was a banana")
        self.assertEqual(sum(result.mapped("product_qty")), 19, "Expected quantity to be 19")
        self.assertEqual(new_ml.product_id, self.banana, "Expected product was a banana")
        self.assertEqual(new_ml.product_qty, 3, "Expected quantity of new ml was three")
        self.assertEqual(quantity, 0, "Expected the un-met quantity to be 0")
        # Check that the largest move line is not split, and  smaller ones are
        self.assertEqual(result.mapped("product_qty"), [17.0, 2.0])

    def test16_move_line_for_qty_partial_split_no_sorting(self):
        """Test when a subset of move lines are to be returned, with one being split, and one original one
        Does not use the default sorting, sort = False
        """
        # Create additional move lines
        pick_info = [{"product": self.banana, "qty": 17}]
        new_picking = self.create_picking(
            self.picking_type_goods_in, products_info=pick_info, confirm=True, assign=True
        )  # Sort the move lines in this case to ensure the smallest is first
        mls_banana = self.banana_move_line | new_picking.move_line_ids
        sorted_mls = mls_banana.sorted(lambda ml: ml.product_qty)
        result, new_ml, quantity = sorted_mls.move_lines_for_qty(19, sort=False)
        # Check returned move line matches requested quantity
        self.assertEqual(result.product_id, self.banana, "Expected product was a banana")
        self.assertEqual(sum(result.mapped("product_qty")), 19, "Expected quantity to be 19")
        self.assertEqual(new_ml.product_id, self.banana, "Expected product was a banana")
        self.assertEqual(new_ml.product_qty, 3, "Expected quantity of new ml was three")
        self.assertEqual(quantity, 0, "Expected the un-met quantity to be 0")
        # Check that the small move line is not split
        self.assertEqual(result.mapped("product_qty"), [5.0, 14.0])

    def test17_move_line_for_qty_exact_qty(self):
        """Check move_lines_for_qty returns the move line of the exact size when possible"""
        mls = self.mls.filtered(lambda ml: ml.product_id == self.banana)
        result, new_ml, quantity = mls.move_lines_for_qty(5)
        self.assertEqual(result.product_id, self.banana)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.product_qty, 5)
        self.assertIsNone(new_ml)
        self.assertEqual(quantity, 0)

    def test18_get_search_domain_not_strict(self):
        """Check _get_search_domain(strict=False) returns what is expected"""
        # Create a quant in stock locations
        test_package_1 = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_1.id
        )
        # Create pick to reserve the quant
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.banana, "qty": 8}],
            assign=True,
            confirm=True,
        )
        line = pick.move_line_ids
        self.assertEqual(len(line), 1)
        # Check _get_domain() with strict = False
        banana_domain = line._get_search_domain(strict=False)
        expected_domain = [
            "&",
            ("location_id", "child_of", line.location_id.id),
            "&",
            ("package_id", "=", line.package_id.id),
            ("product_id", "=", line.product_id.id),
        ]
        self.assertEqual(banana_domain, expected_domain)

    def test19_get_search_domain_strict(self):
        """Check _get_search_domain(strict=True) returns what is expected"""
        # Create a quant in stock locations
        test_package_1 = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_1.id
        )
        # Create pick to reserve the quant
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.banana, "qty": 8}],
            assign=True,
            confirm=True,
        )
        line = pick.move_line_ids
        self.assertEqual(len(line), 1)
        # Check _get_domain() with strict = True
        banana_domain = line._get_search_domain(strict=True)
        expected_domain = [
            "&",
            ("location_id", "=", line.location_id.id),
            "&",
            ("owner_id", "=", False),
            "&",
            ("package_id", "=", line.package_id.id),
            "&",
            ("lot_id", "=", False),
            ("product_id", "=", line.product_id.id),
        ]

        self.assertEqual(banana_domain, expected_domain)
