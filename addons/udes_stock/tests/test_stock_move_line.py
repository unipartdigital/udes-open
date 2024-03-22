from . import common
from odoo.exceptions import ValidationError, UserError


class TestStockMoveLine(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockMoveLine, cls).setUpClass()
        # Order the banana first to allow for sorting checks later on
        cls._pick_info = [
            {"product": cls.banana, "uom_qty": 5},
            {"product": cls.apple, "uom_qty": 4},
        ]
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

    def test_get_quantities_by_key(self):
        """Get the quants related to the move lines"""
        # Set expected goods in picking info
        expected = {self.banana: 5, self.apple: 4}
        # Check it matches with the moves lines of the default goods in picking
        self.assertEqual(self.mls.get_quantities_by_key(), expected)

    def test_get_quantities_by_key_multiple_products(self):
        """Get the quants related to the move lines for multiple products"""
        # Create three quants in stock locations and different packages
        test_package_1 = self.create_package()
        test_package_2 = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=test_package_1.id
        )
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_1.id
        )
        self.create_quant(
            self.apple.id, self.test_stock_location_02.id, 10, package_id=test_package_2.id
        )
        # Create pick to reserve the quants
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 12},
                {"product": self.banana, "uom_qty": 5},
            ],
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

    def test_sort_by_key(self):
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

    def test_sort_by_key_custom(self):
        """Get the move lines sorted by product qty then product id"""
        pick_info = [
            {"product": self.banana, "uom_qty": 5},
            {"product": self.fig, "uom_qty": 4},
            {"product": self.apple, "uom_qty": 5},
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

    def test_split_by_qty_success(self):
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

    def test_split_by_qty_failure(self):
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

    def test_split_by_done_simple(self):
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

    def test_split_by_qty_with_done_qty_success(self):
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

    def test_split_by_qty_with_done_qty_failure(self):
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
        self.assertEqual(e.exception.args[0], msg)

    def test_get_move_lines_done_and_done_and_incomplete(self):
        """Check:
            * get_move_lines_done
            * get_lines_partially_complete
            * get_move_lines_incomplete
        functions works as expected"""
        # Check no done move lines
        self.assertFalse(self.mls.get_lines_done())
        self.assertFalse(self.mls.get_lines_partially_complete())
        self.assertEqual(len(self.mls.get_lines_incomplete()), 2)
        # Complete the apple move
        self.update_move(self.apple_move, 4)
        # Check that one move line is complete
        self.assertEqual(self.mls.get_lines_done(), self.apple_move.move_line_ids)
        self.assertFalse(self.mls.get_lines_partially_complete())
        self.assertEqual(self.mls.get_lines_incomplete(), self.banana_move.move_line_ids)
        # Complete partially the banana move
        self.update_move(self.banana_move, 1)
        # Check that one move line is complete still
        self.assertEqual(self.mls.get_lines_done(), self.apple_move.move_line_ids)
        self.assertEqual(self.mls.get_lines_incomplete(), self.banana_move.move_line_ids)
        self.assertEqual(self.mls.get_lines_partially_complete(), self.banana_move.move_line_ids)
        # Complete the rest of the move line and over receive - update move is cumulative
        self.update_move(self.banana_move, 10)
        # Check all move lines are complete
        self.assertEqual(len(self.mls.get_lines_done()), 2)
        self.assertFalse(self.mls.get_lines_partially_complete())
        self.assertFalse(self.mls.get_lines_incomplete())

    def test_get_quants(self):
        """Check get_quants returns what is expected"""
        # Create three quants in stock locations
        test_package_1 = self.create_package()
        test_package_2 = self.create_package()
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 10, package_id=test_package_1.id
        )
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_1.id
        )
        self.create_quant(
            self.apple.id, self.test_stock_location_02.id, 10, package_id=test_package_2.id
        )
        # Create pick to reserve the quants
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 12},
                {"product": self.banana, "uom_qty": 8},
            ],
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

    def test_move_line_for_qty_simple(self):
        """Check move_lines_for_qty returns the move line if satisfied straightaway"""
        # Get apple move line from default goods in picking
        ml_apple = self.apple_move_line
        result, new_ml, quantity = ml_apple.move_lines_for_qty(4)
        self.assertEqual(result, ml_apple)
        self.assertEqual(result.product_qty, 4)
        self.assertIsNone(new_ml)
        self.assertEqual(quantity, 0)

    def test_move_line_for_qty_split(self):
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

    def test_move_line_for_qty_split_cannot_fulfil(self):
        """Test when a subset of move lines are to be returned, where the quantity > than that in mls"""
        # Get banana move line from default goods in picking
        ml_banana = self.banana_move_line
        result, new_ml, quantity = ml_banana.move_lines_for_qty(11)
        # Check returns move line, and remaining qty needed
        self.assertEqual(result.product_id, self.banana, "Expected product was a banana")
        self.assertEqual(sum(result.mapped("product_qty")), 5, "Expected quantity to be five")
        self.assertEqual(quantity, 6, "Expected the un-met quantity to be six")
        self.assertIsNone(new_ml)

    def test_move_line_for_qty_partial_split_default_sorting(self):
        """Test when a subset of move lines are to be returned, with one being split, and one original one
        Uses the default sorting
        """
        # Create additional move lines in a new picking
        pick_info = [{"product": self.banana, "uom_qty": 17}]
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

    def test_move_line_for_qty_partial_split_no_sorting(self):
        """Test when a subset of move lines are to be returned, with one being split, and one original one
        Does not use the default sorting, sort = False
        """
        # Create additional move lines
        pick_info = [{"product": self.banana, "uom_qty": 17}]
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

    def test_move_line_for_qty_exact_qty(self):
        """Check move_lines_for_qty returns the move line of the exact size when possible"""
        mls = self.mls.filtered(lambda ml: ml.product_id == self.banana)
        result, new_ml, quantity = mls.move_lines_for_qty(5)
        self.assertEqual(result.product_id, self.banana)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.product_qty, 5)
        self.assertIsNone(new_ml)
        self.assertEqual(quantity, 0)

    def test_get_search_domain_not_strict(self):
        """Check _get_search_domain(strict=False) returns what is expected"""
        # Create a quant in stock locations
        test_package_1 = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_1.id
        )
        # Create pick to reserve the quant
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.banana, "uom_qty": 8}],
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

    def test_get_search_domain_strict(self):
        """Check _get_search_domain(strict=True) returns what is expected"""
        # Create a quant in stock locations
        test_package_1 = self.create_package()
        self.create_quant(
            self.banana.id, self.test_stock_location_01.id, 5, package_id=test_package_1.id
        )
        # Create pick to reserve the quant
        pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.banana, "uom_qty": 8}],
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


class TestStockMoveLinePrepareAndMarkMoveLines(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Order the banana first to allow for sorting checks later on
        cls._pick_info = [
            {"product": cls.banana, "uom_qty": 5},
            {"product": cls.apple, "uom_qty": 4},
        ]
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

    def _quantity_reserved_on_a_quant(self, lot_name, location=None):
        """
        Reserved quantity on quants with a lot_name and in location
        """
        Quant = self.env["stock.quant"]

        quants = Quant.search([("lot_id.name", "=", lot_name)])
        if location:
            quant = quants.filtered(lambda q: q.location_id == location)
            reserved_quantity = quant.reserved_quantity
        else:
            reserved_quantity = sum(quants.mapped("reserved_quantity"))
        return reserved_quantity

    def test_by_source_package(self):
        """Combinations having source package and no product_ids.
        Move lines of the source package are returned as one only entry in the result.
        When move lines do not match with the ones of the package it raises ValidationError.
        """
        # Setup data with source package, so better use picking_type_pick
        package = self.create_package()
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 10, package_id=package.id)
        pick_info = [{"product": self.apple, "uom_qty": 5}]
        pick = self.create_picking(
            picking_type=self.picking_type_pick, products_info=pick_info, confirm=True, assign=True
        )
        mls = pick.move_line_ids
        self.assertEqual(mls.package_id, package)
        # Prepare extra parameters for prepare
        result_package = self.create_package()
        location_dest = self.test_goodsout_location_01

        # When no other parameters, the move lines are returned with an empty dict
        empty_res = mls.prepare(package=package)
        self.assertEqual(empty_res[mls], {})

        # When other parameters, the move lines are returned with a dict and them
        res = mls.prepare(
            package=package, result_package=result_package, location_dest=location_dest
        )
        self.assertEqual(res[mls]["result_package_id"], result_package.id)
        self.assertEqual(res[mls]["location_dest_id"], location_dest.id)

        # When move lines do not match raises ValidationError,
        # so get the move lines from the goods-in
        goods_in = self.picking
        other_mls = goods_in.move_line_ids
        with self.assertRaises(ValidationError) as e:
            no_res = other_mls.prepare(package=package)
        msg = f"All package {package.name} move lines cannot be found in picking {goods_in.name}"
        self.assertIn(e.exception.args[0], msg)

        # Mark moves lines as done, only using the res with parameters
        marked = mls.mark_as_done(res[mls])
        self.assertTrue(marked)
        self.assertEqual(mls.qty_done, 5)
        self.assertEqual(mls.result_package_id.id, result_package.id)
        self.assertEqual(mls.location_dest_id.id, location_dest.id)

    def test_no_params(self):
        """Combinations not having source package nor product_ids."""
        goods_in = self.picking
        mls = goods_in.move_line_ids
        apple_ml = self.apple_move_line
        banana_ml = self.banana_move_line
        original_location_dest = apple_ml.location_dest_id
        # When no other parameters, the move lines are returned with an empty dict
        res = mls.prepare()
        self.assertEqual(res[mls], {})

        # Mark moves lines as done with emtpy dict
        marked = mls.mark_as_done(res[mls])
        self.assertTrue(marked)
        self.assertEqual(apple_ml.qty_done, 4)
        self.assertEqual(banana_ml.qty_done, 5)
        self.assertFalse(apple_ml.result_package_id)
        self.assertEqual(apple_ml.location_dest_id, original_location_dest)

    def test_by_product_ids(self):
        """Combinations having product_ids.
        [{"barcode": "PROD01", "uom_qty":1}]
        """
        goods_in = self.picking
        mls = goods_in.move_line_ids
        apple_barcode = self.apple.barcode
        banana_barcode = self.banana.barcode
        apple_ml = self.apple_move_line
        banana_ml = self.banana_move_line
        original_location_dest = self.apple_move_line.location_dest_id
        # Prepare parameters for prepare
        result_package = self.create_package()
        location_dest = self.test_goodsout_location_01
        apple_product_ids = [{"barcode": apple_barcode, "uom_qty": 1}]
        banana_product_ids = [{"barcode": banana_barcode, "uom_qty": 3}]

        # This will split apple_ml and its result will be an empty dict
        apple_res = mls.prepare(product_ids=apple_product_ids)
        self.assertEqual(apple_res[apple_ml]["qty_done"], 1)
        self.assertEqual(len(goods_in.move_line_ids), 3)
        self.assertEqual(apple_ml.product_uom_qty, 1)

        # This will split banana_ml and its result won't be an empty dict
        banana_res = mls.prepare(
            product_ids=banana_product_ids,
            result_package=result_package,
            location_dest=location_dest,
        )
        self.assertEqual(banana_res[banana_ml]["qty_done"], 3)
        self.assertEqual(banana_res[banana_ml]["result_package_id"], result_package.id)
        self.assertEqual(banana_res[banana_ml]["location_dest_id"], location_dest.id)
        self.assertEqual(len(goods_in.move_line_ids), 4)
        self.assertEqual(banana_ml.product_uom_qty, 3)

        # Mark apple moves line as done
        marked = apple_ml.mark_as_done(apple_res[apple_ml])
        self.assertTrue(marked)
        self.assertEqual(apple_ml.qty_done, 1)
        self.assertFalse(apple_ml.result_package_id)
        self.assertEqual(apple_ml.location_dest_id, original_location_dest)
        # Mark banana moves line as done
        marked = banana_ml.mark_as_done(banana_res[banana_ml])
        self.assertTrue(marked)
        self.assertEqual(banana_ml.qty_done, 3)
        self.assertEqual(banana_ml.result_package_id, result_package)
        self.assertNotEqual(banana_ml.location_dest_id, original_location_dest)

    def test_over_mark_error(self):
        """Trying to mark as done more than the quantity in a move line raises ValidationError"""
        banana_ml = self.banana_move_line
        prod_name = self.banana.name
        with self.assertRaises(ValidationError) as e:
            marked = self.banana_move_line.mark_as_done({"qty_done": 100})
        msg = (
            f"Move line {banana_ml.id} for product {prod_name} does not have enough "
            f"quantity: 100 vs 5"
        )
        self.assertEqual(e.exception.args[0], msg)

    def test_swap_serial_lot_name_on_single_move_line(self):
        """
        When prepare is given a different lot_name for a single serial product move_line, and u_tracked_product_swap is turned on, then the resultant move_line values
        will have swapped lot_names
        Moveline 1: 1 x serial 1 --> 1 x serial 2
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        for lot_num in range(1, 6):
            self.create_quant(
                self.strawberry.id,
                location_id=self.test_stock_location_01.id,
                qty=1,
                lot_name=f"{lot_num}",
            )

        product_info = [{"product": self.strawberry, "uom_qty": 1}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productStrawberry", "uom_qty": 1, "lot_names": ["2"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")

        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        self.assertEqual(res[picking.move_line_ids]["lot_name"], "2")
        self.assertEqual(res[picking.move_line_ids]["product_uom_qty"], 1)
        self.assertEqual(res[picking.move_line_ids]["qty_done"], 1)
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["2"])

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.strawberry.name}, Quantity: 1.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.strawberry.name}, Quantity: 1.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking.message_ids[0].body, swap_in_message)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)

    def test_swap_serial_lot_names_on_multiple_move_lines(self):
        """
        When prepare is given different lot_names for multiple serial product move_lines, and u_tracked_product_swap is turned on, then the resultant move_line values
        will have swapped lot_names
        Moveline 1: 1 x serial 1
        Moveline 2: 1 x serial 2 --> 1 x serial 4
        Moveline 3: 1 x serial 3 --> 1 x serial 5
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        for lot_num in range(1, 6):
            self.create_quant(
                self.strawberry.id,
                location_id=self.test_stock_location_01.id,
                qty=1,
                lot_name=f"{lot_num}",
            )
        product_info = [{"product": self.strawberry, "uom_qty": 3}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productStrawberry", "uom_qty": 3, "lot_names": ["1", "4", "5"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")

        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)
        self.assertEqual(sorted(picking.move_line_ids.lot_id.mapped("name")), ["1", "4", "5"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [1.0, 1.0, 1.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [1.0, 1.0, 1.0])

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.strawberry.name}, Quantity: 1.0, Lot/Serial Name: 2 </li>"
        )
        swap_out_text += (
            f"<li>Product: {self.strawberry.name}, Quantity: 1.0, Lot/Serial Name: 3 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.strawberry.name}, Quantity: 1.0, Lot/Serial Name: 4 </li>"
        )
        swap_in_text += (
            f"<li>Product: {self.strawberry.name}, Quantity: 1.0, Lot/Serial Name: 5 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking.message_ids[0].body, swap_in_message)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)

    def test_swap_lot_lot_name_on_single_move_line(self):
        """
        When prepare is given a differrent lot name for a single lot product move_line, and u_tracked_product_swap is turned on, then the resultant move_line value will
        have swapped lot_names
        Moveline 1: 10 x lot 1 --> 10 x lot 2
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        for lot_num in range(1, 6):
            self.create_quant(
                self.tangerine.id,
                location_id=self.test_stock_location_01.id,
                qty=10,
                lot_name=f"{lot_num}",
            )
        product_info = [{"product": self.tangerine, "uom_qty": 10}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productTangerine", "uom_qty": 10, "lot_names": ["2"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")

        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        self.assertEqual(res[picking.move_line_ids]["lot_name"], "2")
        self.assertEqual(res[picking.move_line_ids]["product_uom_qty"], 10)
        self.assertEqual(res[picking.move_line_ids]["qty_done"], 10)
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["2"])

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking.message_ids[0].body, swap_in_message)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)

    def test_swapping_the_lots_on_two_move_lines(self):
        """
        Swap lot when new lot is actually reserved on the move_line of another picking
        The swaps on the second picking below are not manually changed (i.e. things are not scanned in for those picking) but changed as a result of the
        swaps on the first picking.
        Originally:
        Picking 1, Moveline: 10 x lot 1
        Picking 2, Moveline: 10 x lot 2
        Swap:
        Picking 1, Moveline: 10 x lot 1 --> 10 x lot 2
        Picking 2, Moveline: 10 x lot 2 --> 10 x lot 1
        Final:
        Picking 1, Moveline: 10 x lot 2
        Picking 2, Moveline: 10 x lot 1
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        for lot_num in range(1, 6):
            self.create_quant(
                self.tangerine.id,
                location_id=self.test_stock_location_01.id,
                qty=10,
                lot_name=f"{lot_num}",
            )
        product_info = [{"product": self.tangerine, "uom_qty": 10}]
        first_picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )
        second_picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )
        self.assertEqual(first_picking.move_line_ids.lot_id.name, "1")
        self.assertEqual(second_picking.move_line_ids.lot_id.name, "2")

        product_ids = [{"barcode": "productTangerine", "uom_qty": 10, "lot_names": ["2"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")

        res = first_picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)
        self.assertEqual(first_picking.move_line_ids.lot_id.name, "2")
        self.assertEqual(first_picking.move_line_ids.product_uom_qty, 10.0)
        self.assertEqual(first_picking.move_line_ids.qty_done, 10.0)
        self.assertEqual(second_picking.move_line_ids.lot_id.name, "1")
        self.assertEqual(second_picking.move_line_ids.product_uom_qty, 10.0)
        self.assertEqual(second_picking.move_line_ids.qty_done, 0.0)

        self.assertEqual(
            self._quantity_reserved_on_a_quant("1", location=self.test_stock_location_01), 10.0
        )
        self.assertEqual(
            self._quantity_reserved_on_a_quant("2", location=self.test_stock_location_01), 10.0
        )

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(first_picking.message_ids[0].body, swap_in_message)
        self.assertEqual(first_picking.message_ids[1].body, swap_out_message)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(second_picking.message_ids[0].body, swap_in_message)
        self.assertEqual(second_picking.message_ids[1].body, swap_out_message)

    def test_swapping_the_lots_on_two_move_lines_with_partial_qty(self):
        """
        Swap partial quantity of lot when new lot is actually reserved on the move_line of another picking.
        The swaps on the second picking below are not manually changed (i.e. things are not scanned in for those picking) but changed as a result of the
        swaps on the first picking.
        Originally:
        Picking 1, Moveline: 10 x lot 1
        Picking 2, Moveline: 10 x lot 2
        First swap:
        Picking 1: 5 x lot 1 --> 5 x lot 2
        Picking 2: 5 x lot 2 --> 5 x lot 1
        Second swap:
        Picking 1: 5 x lot 1 --> 5 x lot 2
        Picking 2: 5 x lot 2 --> 5 x lot 1
        Final:
        Picking 1, Moveline: 10 x lot 2
        Picking 2, Moveline: 10 x lot 1
        """
        Picking = self.env["stock.picking"]

        self.picking_type_pick.u_allow_swapping_tracked_products = True
        product_info = [{"product": self.tangerine, "uom_qty": 10}]
        new_pickings = Picking.browse()
        for lot_num in range(1, 6):
            self.create_quant(
                self.tangerine.id,
                location_id=self.test_stock_location_01.id,
                qty=10,
                lot_name=f"{lot_num}",
            )
            if lot_num < 3:
                new_pickings |= self.create_picking(
                    self.picking_type_pick, products_info=product_info, assign=True
                )
        first_picking, second_picking = new_pickings
        self.assertEqual(first_picking.move_line_ids.lot_id.name, "1")
        self.assertEqual(second_picking.move_line_ids.lot_id.name, "2")

        product_ids = [{"barcode": "productTangerine", "uom_qty": 5, "lot_names": ["2"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")

        res = first_picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)
        self.assertEqual(second_picking.move_line_ids.mapped("lot_id.name"), ["2", "1"])
        self.assertEqual(second_picking.move_line_ids.mapped("product_uom_qty"), [5.0, 5.0])
        self.assertEqual(second_picking.move_line_ids.mapped("qty_done"), [0.0, 0.0])

        self.assertEqual(
            self._quantity_reserved_on_a_quant("1", location=self.test_stock_location_01), 10.0
        )
        self.assertEqual(
            self._quantity_reserved_on_a_quant("2", location=self.test_stock_location_01), 10.0
        )

        product_ids = [{"barcode": "productTangerine", "uom_qty": 5, "lot_names": ["2"]}]
        res = first_picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(first_picking.move_line_ids.lot_id.name, "2")
        self.assertEqual(first_picking.move_line_ids.mapped("product_uom_qty"), [5.0, 5.0])
        self.assertEqual(first_picking.move_line_ids.mapped("qty_done"), [5.0, 5.0])
        self.assertEqual(second_picking.move_line_ids.lot_id.name, "1")
        self.assertEqual(second_picking.move_line_ids.mapped("product_uom_qty"), [5.0, 5.0])
        self.assertEqual(second_picking.move_line_ids.mapped("qty_done"), [0.0, 0.0])

        self.assertEqual(
            self._quantity_reserved_on_a_quant("1", location=self.test_stock_location_01), 10.0
        )
        self.assertEqual(
            self._quantity_reserved_on_a_quant("2", location=self.test_stock_location_01), 10.0
        )

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(first_picking.message_ids[0].body, swap_in_message)
        self.assertEqual(first_picking.message_ids[1].body, swap_out_message)
        self.assertEqual(first_picking.message_ids[2].body, swap_in_message)
        self.assertEqual(first_picking.message_ids[3].body, swap_out_message)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(second_picking.message_ids[0].body, swap_in_message)
        self.assertEqual(second_picking.message_ids[1].body, swap_out_message)
        self.assertEqual(second_picking.message_ids[2].body, swap_in_message)
        self.assertEqual(second_picking.message_ids[3].body, swap_out_message)

    def test_expect_one_lot_but_receieve_two_lots(self):
        """
        Expect one lot, but get two lots to make up the moveline
        Originally:
        Moveline: 10 x lot 1
        First Swap:
        5 x lot 1 --> 5 x lot 2
        Second Swap:
        5 x lot 1 --> 5 x lot 3
        Final:
        Moveline 1: 5 x lot 2
        Moveline 2: 5 x lot 3
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True

        quant_one = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=10, lot_name="1"
        )
        quant_two = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="2"
        )
        quant_three = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="3"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 10}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )
        self.assertEqual(len(picking.move_line_ids), 1)
        self.assertEqual(picking.move_line_ids.product_uom_qty, 10)

        product_ids = [{"barcode": "productTangerine", "uom_qty": 5, "lot_names": ["2"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(res[picking.move_line_ids[0]]["lot_name"], "2")
        self.assertEqual(res[picking.move_line_ids[0]]["product_uom_qty"], 5.0)
        self.assertEqual(res[picking.move_line_ids[0]]["qty_done"], 5.0)

        product_ids = [{"barcode": "productTangerine", "uom_qty": 5, "lot_names": ["3"]}]
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(res[picking.move_line_ids[1]]["lot_name"], "3")
        self.assertEqual(res[picking.move_line_ids[1]]["product_uom_qty"], 5.0)
        self.assertEqual(res[picking.move_line_ids[1]]["qty_done"], 5.0)

        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["2", "3"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [5.0, 5.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [5.0, 5.0])

        self.assertEqual(quant_one.reserved_quantity, 0.0)
        self.assertEqual(quant_two.reserved_quantity, 5.0)
        self.assertEqual(quant_three.reserved_quantity, 5.0)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_in_text_2 = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 3 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        swap_in_message_2 = swap_in_title + swap_in_text_2
        self.assertEqual(picking.message_ids[0].body, swap_in_message_2)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)
        self.assertEqual(picking.message_ids[2].body, swap_in_message)
        self.assertEqual(picking.message_ids[3].body, swap_out_message)

    def test_expect_two_lots_be_scanned_in_but_only_receive_one_different_lot(self):
        """
        Expect two lots be scanned in, but only receive one different lot
        Originally:
        Moveline 1: 5 x lot 1
        Moveline 2: 5 x lot 2
        Swap:
        5 x lot 1, 5 x lot 2 --> 10 x lot 3
        Final:
        Moveline 1: 10 x lot 3
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        quant_one = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="1"
        )
        quant_two = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="2"
        )
        quant_three = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=10, lot_name="3"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 10}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )
        self.assertEqual(len(picking.move_line_ids), 2)

        product_ids = [{"barcode": "productTangerine", "uom_qty": 10, "lot_names": ["3"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 1)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["3"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [10.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [10.0])

        self.assertEqual(quant_one.reserved_quantity, 0.0)
        self.assertEqual(quant_two.reserved_quantity, 0.0)
        self.assertEqual(quant_three.reserved_quantity, 10.0)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li>"
        )
        swap_out_text += (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 3 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking.message_ids[0].body, swap_in_message)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)

    def test_swap_in_lot_quantity_with_more_quantity_than_many_move_lines(self):
        """
        Swap in a quantity of a lot which is greater than the quantity on multiple move_lines
        Originally:
        Moveline 1: 1 x lot 1
        Moveline 2: 1 x lot 2
        Moveline 3: 5 x lot 3
        Moveline 4: 3 x lot 4
        Moveline 5: 5 x lot 5
        First Swap:
        1 x lot 1, 1 x lot 2, 5 x lot 3, 3 x lot 4 --> 10 x lot 6
        Second Swap:
        5 x lot 5 --> 5 x lot 7
        Final:
        Moveline 1: 10 x lot 6
        Moveline 2: 5 x lot 7
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        # Lots to go on picking
        quant_one = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=1, lot_name="1"
        )
        quant_two = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=1, lot_name="2"
        )
        quant_three = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="3"
        )
        quant_four = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=3, lot_name="4"
        )
        quant_five = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="5"
        )
        # Lots to be swapped in
        quant_six = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=10, lot_name="6"
        )
        quant_seven = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="7"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 15}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["1", "2", "3", "4", "5"])

        product_ids = [{"barcode": "productTangerine", "uom_qty": 10, "lot_names": ["6"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["5", "6"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [5.0, 10.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [0.0, 10.0])

        product_ids = [{"barcode": "productTangerine", "uom_qty": 5.0, "lot_names": ["7"]}]
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["7", "6"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [5.0, 10.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [5.0, 10.0])

        self.assertEqual(quant_one.reserved_quantity, 0.0)
        self.assertEqual(quant_two.reserved_quantity, 0.0)
        self.assertEqual(quant_three.reserved_quantity, 0.0)
        self.assertEqual(quant_four.reserved_quantity, 0.0)
        self.assertEqual(quant_five.reserved_quantity, 0.0)
        self.assertEqual(quant_six.reserved_quantity, 10.0)
        self.assertEqual(quant_seven.reserved_quantity, 5.0)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 1.0, Lot/Serial Name: 1 </li>"
        )
        swap_out_text += (
            f"<li>Product: {self.tangerine.name}, Quantity: 1.0, Lot/Serial Name: 2 </li>"
        )
        swap_out_text += (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 3 </li>"
        )
        swap_out_text += (
            f"<li>Product: {self.tangerine.name}, Quantity: 3.0, Lot/Serial Name: 4 </li></ul>"
        )
        swap_out_text_2 = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 5 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_out_message_2 = swap_out_title + swap_out_text_2
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 6 </li></ul>"
        )
        swap_in_text_2 = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 7 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        swap_in_message_2 = swap_in_title + swap_in_text_2
        self.assertEqual(picking.message_ids[0].body, swap_in_message_2)
        self.assertEqual(picking.message_ids[1].body, swap_out_message_2)
        self.assertEqual(picking.message_ids[2].body, swap_in_message)
        self.assertEqual(picking.message_ids[3].body, swap_out_message)

    def test_swap_in_lot_quantity_which_partially_covers_a_moveline(self):
        """
        Swap in a quantity of lot which will partially cover a moveline
        Originally:
        Moveline 1: 5 x lot 1
        Moveline 2: 5 x lot 2
        First Swap:
        5 x lot 1, 1 x lot 2 --> 6 x lot 3
        Second Swap:
        4 x lot 2 --> 4 x lot 4
        Final:
        Moveline 1: 6 x lot 3
        Moveline 2: 4 x lot 4
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True

        quant_one = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="1"
        )
        quant_two = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="2"
        )
        quant_three = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=6, lot_name="3"
        )
        quant_four = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=4, lot_name="4"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 10}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productTangerine", "uom_qty": 6.0, "lot_names": ["3"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["2", "3"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [4.0, 6.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [0.0, 6.0])

        product_ids = [{"barcode": "productTangerine", "uom_qty": 4.0, "lot_names": ["4"]}]
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["4", "3"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [4.0, 6.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [4.0, 6.0])

        self.assertEqual(quant_one.reserved_quantity, 0.0)
        self.assertEqual(quant_two.reserved_quantity, 0.0)
        self.assertEqual(quant_three.reserved_quantity, 6.0)
        self.assertEqual(quant_four.reserved_quantity, 4.0)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li>"
        )
        swap_out_text += (
            f"<li>Product: {self.tangerine.name}, Quantity: 1.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_text_2 = (
            f"<li>Product: {self.tangerine.name}, Quantity: 4.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_out_message_2 = swap_out_title + swap_out_text_2
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 6.0, Lot/Serial Name: 3 </li></ul>"
        )
        swap_in_text_2 = (
            f"<li>Product: {self.tangerine.name}, Quantity: 4.0, Lot/Serial Name: 4 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        swap_in_message_2 = swap_in_title + swap_in_text_2
        self.assertEqual(picking.message_ids[0].body, swap_in_message_2)
        self.assertEqual(picking.message_ids[1].body, swap_out_message_2)
        self.assertEqual(picking.message_ids[2].body, swap_in_message)
        self.assertEqual(picking.message_ids[3].body, swap_out_message)

    def test_complete_picking_with_serial_product_then_create_another_picking_and_swap_in_previous_lot_id(
        self,
    ):
        """
        Validate a picking with a serial product with a lot_id, then swap that lot_id into a new picking and validate to make sure there
        are no errors. This test ensures that previously used lots are not withheld from being swapped in.
        Putaway picking:
        Picking 1, moveline: 1 x lot 1 -> State = Done (picking has been completed)
        Pick picking:
        Picking 2, moveline: 1 x lot 2 --> 1 x lot 1
        """
        Quant = self.env["stock.quant"]
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        # Create quant_two first to ensure it gets reserved on Pick, as lots are reserved in the order of in_date
        quant_two = self.create_quant(
            self.strawberry.id,
            location_id=self.test_stock_location_01.id,
            qty=1,
            lot_name="2",
        )
        self.create_quant(
            self.strawberry.id,
            location_id=self.test_received_location_01.id,
            qty=1,
            lot_name="1",
        )

        product_info = [{"product": self.strawberry, "uom_qty": 1}]
        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=product_info,
            location_dest_id=self.test_stock_location_01.id,
            assign=True,
        )
        picking.move_line_ids.write({"qty_done": 1.0})
        picking.validate_picking()

        # Create a picking and swap-in the serial product that was used previously
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=product_info,
            location_dest_id=self.test_goodsout_location_01.id,
            assign=True,
        )
        self.assertEqual(picking.move_line_ids.lot_id.name, "2")
        product_ids = [{"barcode": "productStrawberry", "uom_qty": 1, "lot_names": ["1"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")

        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(picking.move_line_ids.qty_done, 1.0)
        self.assertEqual(picking.move_line_ids.product_uom_qty, 1.0)
        self.assertEqual(picking.move_line_ids.lot_id.name, "1")

        self.assertEqual(Quant.search([])[1].reserved_quantity, 1.0)
        self.assertEqual(quant_two.reserved_quantity, 0.0)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.strawberry.name}, Quantity: 1.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.strawberry.name}, Quantity: 1.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking.message_ids[0].body, swap_in_message)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)

        # Picking was validated okay
        picking.validate_picking()
        self.assertEqual(picking.state, "done")

    def test_ensure_lot_gets_swapped_correctly_with_many_of_same_lot_in_progress(self):
        """
        Have two pickings in the "assigned" state with the same lot, one with qty_done and one without.
        Then create a picking for a second lot, but swap in the first lot during picking. This should swap the lots on the picking
        with no qty_done and the new picking, the qty_done picking should remain the same. Ensure lots are not swapped
        on movelines with qty done set.
        Originally:
        Picking 1: 5 x lot 1, qty_done = 5
        Picking 2: 5 x lot 1, qty_done = 0
        Picking 3: 5 x lot 2, qty_done = 0
        Swap:
        Picking 3: 5 x lot 2 --> 5 x lot 1
        Final:
        Picking 1: 5 x lot 1, qty_done = 5
        Picking 2: 5 x lot 2, qty_done = 5
        Picking 3: 5 x lot 1, qty_done = 0
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        quant_one = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5.0, lot_name="1"
        )
        quant_two = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5.0, lot_name="2"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 5.0}]
        picking_qty_done = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )
        product_ids = [{"barcode": "productTangerine", "uom_qty": 5.0, "lot_names": ["1"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking_qty_done.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        product_info = [{"product": self.tangerine, "uom_qty": 5.0}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )
        self.assertEqual(picking.move_line_ids.lot_id.name, "2")

        quant_one.write({"quantity": 15.0})

        product_info = [{"product": self.tangerine, "uom_qty": 5.0}]
        picking_no_qty_done = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productTangerine", "uom_qty": 5.0, "lot_names": ["1"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES2")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(picking.move_line_ids.lot_id.name, "1")
        self.assertEqual(picking.move_line_ids.product_uom_qty, 5.0)
        self.assertEqual(picking.move_line_ids.qty_done, 5.0)

        self.assertEqual(picking_no_qty_done.move_line_ids.lot_id.name, "2")
        self.assertEqual(picking_no_qty_done.move_line_ids.product_uom_qty, 5.0)
        self.assertEqual(picking_no_qty_done.move_line_ids.qty_done, 0.0)

        self.assertEqual(picking_qty_done.move_line_ids.lot_id.name, "1")
        self.assertEqual(picking_qty_done.move_line_ids.product_uom_qty, 5.0)
        self.assertEqual(picking_qty_done.move_line_ids.qty_done, 5.0)

        self.assertEqual(quant_one.reserved_quantity, 10.0)
        self.assertEqual(quant_two.reserved_quantity, 5.0)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking_no_qty_done.message_ids[0].body, swap_in_message)
        self.assertEqual(picking_no_qty_done.message_ids[1].body, swap_out_message)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking.message_ids[0].body, swap_in_message)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)

    def test_over_receive_on_a_lot_with_swapping_tracked_products_on(self):
        """
        Expect two movelines of same quantity but overpick on one of the movelines for double the quantity.
        Originally:
        moveline 1: 5 x lot 1
        moveline 2: 5 x lot 2
        Swap:
        5 x lot 1, 5 x lot 2 --> 10 x lot 2
        Final:
        moveline: 10 x lot 2
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        quant_one = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="1"
        )
        quant_two = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=15, lot_name="2"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 10}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productTangerine", "uom_qty": 10, "lot_names": ["2"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 1)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["2"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [10.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [10.0])

        self.assertEqual(quant_one.reserved_quantity, 0.0)
        self.assertEqual(quant_two.reserved_quantity, 10.0)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li>"
        )
        swap_out_text += (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 10.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking.message_ids[0].body, swap_in_message)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)

    def test_over_receive_on_a_lot_such_that_next_moveline_is_partially_fulfilled(self):
        """
        Expect two movelines of same quantity but overpick on one of the movelines with quantity that
        partially picks the second moveline.
        Originally:
        moveline 1: 5 x lot 1
        moveline 2: 5 x lot 2
        Swap:
        5 x lot 1, 3 x lot 2 --> 8 x lot 2
        Final:
        moveline: 8 x lot 2, 2 x lot 2
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        quant_one = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="1"
        )
        quant_two = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=15, lot_name="2"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 10}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productTangerine", "uom_qty": 8, "lot_names": ["2"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["2"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [2.0, 8.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [0.0, 8.0])

        product_ids = [{"barcode": "productTangerine", "uom_qty": 2, "lot_names": ["2"]}]
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["2"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [2.0, 8.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [2.0, 8.0])

        self.assertEqual(quant_one.reserved_quantity, 0.0)
        self.assertEqual(quant_two.reserved_quantity, 10.0)

        swap_out_title = "<p>Tracked Products Swapped Out: </p><ul>"
        swap_out_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 5.0, Lot/Serial Name: 1 </li>"
        )
        swap_out_text += (
            f"<li>Product: {self.tangerine.name}, Quantity: 3.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_out_message = swap_out_title + swap_out_text
        swap_in_title = "<p>Tracked Products Swapped In: </p><ul>"
        swap_in_text = (
            f"<li>Product: {self.tangerine.name}, Quantity: 8.0, Lot/Serial Name: 2 </li></ul>"
        )
        swap_in_message = swap_in_title + swap_in_text
        self.assertEqual(picking.message_ids[0].body, swap_in_message)
        self.assertEqual(picking.message_ids[1].body, swap_out_message)

    def test_normal_serial_process_works_when_tracked_product_swapping_turned_on(self):
        """
        Ensure the normal serial process works when turning on tracked product swapping.
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        quant_one = self.create_quant(
            self.strawberry.id, location_id=self.test_stock_location_01.id, qty=1, lot_name="1"
        )
        quant_two = self.create_quant(
            self.strawberry.id, location_id=self.test_stock_location_01.id, qty=1, lot_name="2"
        )

        product_info = [{"product": self.strawberry, "uom_qty": 2}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productStrawberry", "uom_qty": 2, "lot_names": ["1", "2"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["1", "2"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [1.0, 1.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [1.0, 1.0])

        self.assertEqual(quant_one.reserved_quantity, 1.0)
        self.assertEqual(quant_two.reserved_quantity, 1.0)

    def test_normal_lot_process_works_when_tracked_product_swapping_turned_on(self):
        """
        Ensure the normal lot process works when turning on tracked product swapping.
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        quant_one = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=10, lot_name="1"
        )
        quant_two = self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=10, lot_name="2"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 20}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productTangerine", "uom_qty": 10, "lot_names": ["1"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)
        product_ids = [{"barcode": "productTangerine", "uom_qty": 10, "lot_names": ["2"]}]
        res = picking.move_line_ids.prepare(
            product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
        )
        for mls, mls_values in res.items():
            mls.mark_as_done(mls_values)

        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.lot_id.mapped("name"), ["1", "2"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [10.0, 10.0])
        self.assertEqual(picking.move_line_ids.mapped("qty_done"), [10.0, 10.0])

        self.assertEqual(quant_one.reserved_quantity, 10.0)
        self.assertEqual(quant_two.reserved_quantity, 10.0)

    def test_user_cannot_swap_in_more_stock_then_on_the_system(self):
        """
        Ensure the user receives an error message if they somehow swap in more stock than is available
        on the system.
        quant: 5 x lot 1
        moveline: 6 x lot 1 --> 6 x lot 1 - Error as on 5 of lot 1 on system
        """
        self.picking_type_pick.u_allow_swapping_tracked_products = True
        self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="1"
        )
        self.create_quant(
            self.tangerine.id, location_id=self.test_stock_location_01.id, qty=5, lot_name="2"
        )

        product_info = [{"product": self.tangerine, "uom_qty": 6}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=product_info, assign=True
        )

        product_ids = [{"barcode": "productTangerine", "uom_qty": 6, "lot_names": ["1"]}]
        location = self.test_stock_location_01
        pallet_to_pick_onto = self.create_package(name="UDES1")

        with self.assertRaises(UserError):
            picking.move_line_ids.prepare(
                product_ids=product_ids, location=location, result_package=pallet_to_pick_onto
            )


class TestFindMoveLines(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pick_info = [
            {"product": cls.banana, "uom_qty": 5},
            {"product": cls.apple, "uom_qty": 4},
            {"product": cls.strawberry, "uom_qty": 3},
            {"product": cls.tangerine, "uom_qty": 10},
        ]
        cls.package = cls.create_package()
        cls.create_quant(cls.banana.id, cls.test_stock_location_01.id, 5)
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 4)
        cls.create_quant(cls.strawberry.id, cls.test_stock_location_01.id, 1, lot_name="sn01")
        cls.create_quant(cls.strawberry.id, cls.test_stock_location_01.id, 1, lot_name="sn02")
        cls.create_quant(cls.strawberry.id, cls.test_stock_location_02.id, 1, lot_name="sn03")
        cls.create_quant(cls.tangerine.id, cls.test_stock_location_01.id, 5, lot_name="lot01")
        cls.create_quant(
            cls.tangerine.id,
            cls.test_stock_location_01.id,
            5,
            lot_name="lot02",
            package_id=cls.package.id,
        )
        cls.picking = cls.create_picking(
            cls.picking_type_pick, products_info=pick_info, confirm=True, assign=True
        )

    def test_find_by_product(self):
        """Find move lines only by product key"""
        mls = self.picking.move_line_ids
        apple_ml = mls.filtered(lambda ml: ml.product_id == self.apple)
        banana_ml = mls.filtered(lambda ml: ml.product_id == self.banana)
        strawberry_mls = mls.filtered(lambda ml: ml.product_id == self.strawberry)
        tangerine_mls = mls.filtered(lambda ml: ml.product_id == self.tangerine)

        # Find ml for all apples: same as apple_ml
        mls_fulfill, new_ml = mls._find_move_lines(4, self.apple)
        self.assertEqual(mls_fulfill, apple_ml)
        self.assertFalse(new_ml)
        # Find ml for 3 apples: apple_ml gets split
        mls_fulfill, new_ml = mls._find_move_lines(3, self.apple)
        self.assertEqual(mls_fulfill, apple_ml)
        self.assertEqual(mls_fulfill.product_uom_qty, 3)
        self.assertTrue(new_ml)
        self.assertEqual(new_ml.product_uom_qty, 1)

        # Find ml for all bananas: same as banana_ml
        mls_fulfill, new_ml = mls._find_move_lines(5, self.banana)
        self.assertEqual(mls_fulfill, banana_ml)
        self.assertFalse(new_ml)
        # Find ml for 2 bananas: banana_ml gets split
        mls_fulfill, new_ml = mls._find_move_lines(2, self.banana)
        self.assertEqual(mls_fulfill, banana_ml)
        self.assertEqual(mls_fulfill.product_uom_qty, 2)
        self.assertTrue(new_ml)
        self.assertEqual(new_ml.product_uom_qty, 3)

        # Find all strawberry: same as strawberry_mls
        mls_fulfill, new_ml = mls._find_move_lines(3, self.strawberry)
        self.assertEqual(mls_fulfill, strawberry_mls)
        self.assertFalse(new_ml)
        # Find ml for 1 strawberry: one of the strawberry_mls without split since their qty is 1
        mls_fulfill, new_ml = mls._find_move_lines(1, self.strawberry)
        self.assertEqual(len(mls_fulfill), 1)
        self.assertEqual(mls_fulfill.product_uom_qty, 1)
        self.assertIn(mls_fulfill, strawberry_mls)
        self.assertFalse(new_ml)

        # Find all tangerines: same as tangerine_mls
        mls_fulfill, new_ml = mls._find_move_lines(10, self.tangerine)
        self.assertEqual(mls_fulfill, tangerine_mls)
        self.assertFalse(new_ml)
        # Find ml for 7 tangerines: same as tangerine_mls but one gets split
        mls_fulfill, new_ml = mls._find_move_lines(7, self.tangerine)
        self.assertEqual(mls_fulfill, tangerine_mls)
        self.assertTrue(new_ml)
        self.assertEqual(new_ml.product_uom_qty, 3)

    def test_find_by_package(self):
        """Find move lines by product and package"""
        mls = self.picking.move_line_ids
        package_mls = mls.filtered(lambda ml: ml.package_id == self.package)

        # Find all tangerines in the package
        mls_fulfill, new_ml = mls._find_move_lines(5, self.tangerine, package=self.package)
        self.assertEqual(mls_fulfill, package_mls)
        self.assertFalse(new_ml)

    def test_find_by_lot_name(self):
        """Find move lines by product and lot_name"""
        mls = self.picking.move_line_ids
        lot01_ml = mls.filtered(lambda ml: ml.lot_id.name == "lot01")
        lot02_ml = mls.filtered(lambda ml: ml.lot_id.name == "lot02")
        sn01_ml = mls.filtered(lambda ml: ml.lot_id.name == "sn01")
        sn02_ml = mls.filtered(lambda ml: ml.lot_id.name == "sn02")
        sn03_ml = mls.filtered(lambda ml: ml.lot_id.name == "sn03")

        # Find all tangerines for lot01: same as lot01_ml
        mls_fulfill, new_ml = mls._find_move_lines(5, self.tangerine, lot_name="lot01")
        self.assertEqual(mls_fulfill, lot01_ml)
        self.assertFalse(new_ml)
        # Find ml for 3 tangerines of lot02: same as lot02_ml but gets split
        mls_fulfill, new_ml = mls._find_move_lines(3, self.tangerine, lot_name="lot02")
        self.assertEqual(mls_fulfill, lot02_ml)
        self.assertTrue(new_ml)
        self.assertEqual(new_ml.product_uom_qty, 2)

        # Find all strawberries for sn01: same as sn01_ml
        mls_fulfill, new_ml = mls._find_move_lines(1, self.strawberry, lot_name="sn01")
        self.assertEqual(mls_fulfill, sn01_ml)
        self.assertFalse(new_ml)
        # Find all strawberries for sn02: same as sn02_ml
        mls_fulfill, new_ml = mls._find_move_lines(1, self.strawberry, lot_name="sn02")
        self.assertEqual(mls_fulfill, sn02_ml)
        self.assertFalse(new_ml)
        # Find all strawberries for sn03: same as sn03_ml
        mls_fulfill, new_ml = mls._find_move_lines(1, self.strawberry, lot_name="sn03")
        self.assertEqual(mls_fulfill, sn03_ml)
        self.assertFalse(new_ml)

    def test_find_by_location(self):
        """Find move lines by product and location"""
        mls = self.picking.move_line_ids
        location01_mls = mls.filtered(
            lambda ml: ml.location_id == self.test_stock_location_01
            and ml.product_id == self.strawberry
        )
        location02_mls = mls.filtered(
            lambda ml: ml.location_id == self.test_stock_location_02
            and ml.product_id == self.strawberry
        )

        # Find all strawberries in test_stock_location_01
        mls_fulfill, new_ml = mls._find_move_lines(
            2, self.strawberry, location=self.test_stock_location_01
        )
        self.assertEqual(mls_fulfill, location01_mls)
        self.assertEqual(len(mls_fulfill), 2)
        self.assertFalse(new_ml)
        # Find all strawberries in test_stock_location_02
        mls_fulfill, new_ml = mls._find_move_lines(
            1, self.strawberry, location=self.test_stock_location_02
        )
        self.assertEqual(mls_fulfill, location02_mls)
        self.assertEqual(len(mls_fulfill), 1)
        self.assertFalse(new_ml)


class TestMergeMoveLines(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_merge_move_lines_by_lot(self):
        """Merge move lines when there are 2 move lines of same lot"""
        pick_info = [
            {"product": self.tangerine, "uom_qty": 10},
        ]
        # Setting up pick and making sure the same lot is used for when reserving both picks.
        self.create_quant(self.tangerine.id, self.test_stock_location_01.id, 5, lot_name="lot01")
        self.create_quant(self.tangerine.id, self.test_stock_location_01.id, 5, lot_name="lot02")
        picking = self.create_picking(
            self.picking_type_pick, products_info=pick_info, confirm=True, assign=True
        )
        # Asserting that both picks are created and reserved as expected.
        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(picking.move_line_ids.mapped("lot_id.name"), ["lot01", "lot02"])
        self.assertEqual(picking.move_line_ids.mapped("product_uom_qty"), [5.0, 5.0])
        # Write picking move lines to same lot, so we can test merge lots method.
        lot = picking.move_line_ids[0].lot_id
        picking.move_line_ids.lot_id.quant_ids.write({"quantity": 10})
        self.assertEqual(picking.move_line_ids.lot_id.quant_ids.mapped("quantity"), [10.0, 10.0])
        picking.move_line_ids.write({"lot_id": lot.id})
        move_line = picking.move_line_ids._merge_move_lines()
        self.assertEqual(len(picking.move_line_ids), 1)
        self.assertEqual(picking.move_line_ids, move_line)
        self.assertEqual(move_line.lot_id, lot)
        self.assertEqual(move_line.product_uom_qty, 10.0)
