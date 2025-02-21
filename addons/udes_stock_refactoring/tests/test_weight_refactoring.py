from odoo.addons.udes_stock.tests import common


class RefactoringByWeightBase(common.BaseUDES):
    def assert_weight_not_exceeded(self, pickings):
        """Helper function to ensure the weight limit of the picking type is not exceeded by the picking."""
        weight_limit = self.picking_type_pick.u_assign_refactor_constraint_value
        for picking in pickings:
            with self.subTest(picking=picking):
                weight_sum = 0
                for move in picking.move_lines:
                    weight_sum += move.product_uom_qty * move.product_id.weight
                check_good = weight_sum <= weight_limit
                # Handle single product exceeding case.
                if (
                    not check_good
                    and len(picking.move_lines) == 1
                    and picking.move_lines.product_uom_qty == 1
                ):
                    check_good = True
                self.assertEqual(
                    check_good,
                    True,
                    "Multi-product/qty weight limit of %s exceeded, got %s"
                    % (weight_limit, weight_sum),
                )


class TestRefactoringConfirmSplittingWeight(RefactoringByWeightBase):
    """Tests splitting by maximum weight."""

    @classmethod
    def setUpClass(cls):
        """
        Split picking to maximum weight
        """
        super().setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.picking_type_pick.write(
            {
                "u_post_confirm_action": "by_maximum_weight",
                "u_assign_refactor_constraint_value": 2,
            }
        )
        # Configure product weights.
        cls.apple.weight = 1
        cls.banana.weight = 1
        cls.cherry.weight = 3
        # Set 'Units' rounding to 1, because we don't want to allow transfers for anything under a unit.
        cls.apple.uom_id.rounding = 1

        cls.picking = cls.create_picking(cls.picking_type_pick)
        cls.pick_domain = [("picking_type_id", "=", cls.picking_type_pick.id)]

    def test_split_by_weight_equally(self):
        """Ensure a pick is split according to maximum weight"""
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 10)
        products_info = [{"product": self.apple, "uom_qty": 10}]
        self.create_move(self.picking, products_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)
        # Check each picking is only for 2 products
        self.assertEqual(len(all_pickings), 5)
        self.assertTrue(
            all([sum(pick.move_lines.mapped("product_uom_qty")) == 2 for pick in all_pickings])
        )
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_unequally(self):
        """
        Ensure a pick is split according to maximum weight
        when it doesn't divide equally
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 7)
        products_info = [{"product": self.apple, "uom_qty": 7}]
        self.create_move(self.picking, products_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check pickings are split into 3 pickings for 2 apples each, and 1 picking for 1 apple.
        self.assertEqual(len(all_pickings), 4)
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [2, 2, 2, 1])
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_unequally_2(self):
        """
        Dave scenario A:
        Apple weight 0.2
        20kg split weight
        101x apples on pick
        """
        self.picking_type_pick.u_assign_refactor_constraint_value = 20
        self.apple.weight = 0.2
        products_info = [{"product": self.apple, "uom_qty": 101}]
        self.create_move(self.picking, products_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)
        self.assertEqual(len(all_pickings), 2)
        # Ensure one pick is for 100 and one is for 1
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(100, 0), (1, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_unequally_3(self):
        """
        Dave scenario B
        Apple weight 10
        Banana weight 1
        Cherry weight 0
        20kg split weight
        1x apple, 11x bananas, 1x cherry on pick
        """
        self.picking_type_pick.u_assign_refactor_constraint_value = 20
        self.apple.weight = 10
        self.banana.weight = 1
        self.cherry.weight = 0

        apples_info = [{"product": self.apple, "uom_qty": 1}]
        bananas_info = [{"product": self.banana, "uom_qty": 11}]
        cherries_info = [{"product": self.cherry, "uom_qty": 1}]

        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.create_move(self.picking, cherries_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)
        self.assertEqual(len(all_pickings), 2)
        # Ensure one pick is for 1 apple and 10 bananas, the other pick is for 1 banana and 1 cherry
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(11, 0), (2, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        # Ensure no lines have 0 remaining qty.
        self.assertEqual(0 not in all_pickings.move_lines.mapped("product_uom_qty"), True)
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_unequally_4(self):
        """
        Apple weight 20
        Banana weight 1
        20kg split weight
        1x apple, 1x bananas
        """
        self.picking_type_pick.u_assign_refactor_constraint_value = 20
        self.apple.weight = 20
        self.banana.weight = 1

        apples_info = [{"product": self.apple, "uom_qty": 1}]
        bananas_info = [{"product": self.banana, "uom_qty": 1}]

        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)
        self.assertEqual(len(all_pickings), 2)
        # Ensure one pick is for an apple, and one pick is for a banana
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(1, 0), (1, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_unequally_5(self):
        """
        Apple weight 1
        Banana weight 10
        Cherry weight 24
        50kg split weight
        20x apple, 4x banana, 2x cherry
        """
        self.picking_type_pick.u_assign_refactor_constraint_value = 50
        self.apple.weight = 1
        self.banana.weight = 10
        self.cherry.weight = 24

        apples_info = [{"product": self.apple, "uom_qty": 20}]
        bananas_info = [{"product": self.banana, "uom_qty": 4}]
        cherries_info = [{"product": self.cherry, "uom_qty": 2}]

        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.create_move(self.picking, cherries_info)
        self.picking.action_confirm()
        all_pickings = self.Picking.search(self.pick_domain)
        self.assertEqual(len(all_pickings), 3)
        # Ensure one pick is for 10 apples and 4 bananas,
        # one pick is for 2 cherries, and one pick is for 10 apples.
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(4, 0), (20, 0), (2, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_partial_reserve(self):
        """
        Ensure a pick is split according to maximum weight
        even for unreserved moves
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 7)
        products_info = [{"product": self.apple, "uom_qty": 10}]
        self.create_move(self.picking, products_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check pickings are split into 3 pickings for 2 apples each, 1 picking for 1 apple,
        # and 1 unreserved picking for 3 apples.
        self.assertEqual(len(all_pickings), 5)
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [2, 2, 2, 2, 2])
        all_pickings.action_assign()
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(2, 1), (2, 2), (2, 2), (2, 2), (2, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        # Check that there is only one picking which is not reserved
        unreserved_picking = all_pickings.filtered(lambda p: p.state == "confirmed")
        self.assertEqual(len(unreserved_picking), 1)
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_mixed_products(self):
        """
        Ensure when using multiple products the pick still splits by weight
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 5)
        apples_info = [{"product": self.apple, "uom_qty": 5}]
        bananas_info = [{"product": self.banana, "uom_qty": 5}]
        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check there are 2 pickings for 2 apples each, 2 pickings for 2 bananas each,
        # and 1 picking for an apple and banana
        self.assertEqual(len(all_pickings), 5)
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [2, 2, 2, 2, 2])
        # Check that one picking is for 1 banana and 1 apple
        mixed_picking = all_pickings.filtered(lambda p: len(p.move_lines) == 2)
        self.assertEqual(len(mixed_picking), 1)
        self.assertCountEqual(
            mixed_picking.move_lines.mapped("product_id").ids, (self.apple + self.banana).ids
        )
        self.assertEqual(mixed_picking.move_lines.mapped("product_uom_qty"), [1, 1])

    def test_split_by_weight_mixed_products_partial_reserve(self):
        """
        Ensure when using multiple products the pick still splits by weight
        with any unreserved quantities moved to a seprate picking
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 5)
        apples_info = [{"product": self.apple, "uom_qty": 7}]
        bananas_info = [{"product": self.banana, "uom_qty": 8}]
        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check each picking has a maximum quantity of 2
        self.assertEqual(len(all_pickings), 8)
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [2, 2, 2, 2, 2, 2, 2, 1])
        all_pickings.action_assign()
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [
            (2, 0),
            (2, 1),
            (2, 2),
            (2, 2),
            (2, 1),
            (2, 2),
            (2, 2),
            (1, 0),
        ]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        # Check that there are pickings which are not reserved but still have been split by weight of the moves.
        unreserved_pickings = all_pickings.filtered(lambda p: p.state == "confirmed")
        self.assertEqual(len(unreserved_pickings), 2)
        moves = unreserved_pickings.move_lines
        self.assertEqual(len(moves), 2)
        move_format = [(m.product_id, m.product_uom_qty, m.reserved_availability) for m in moves]
        expected_move_format = [(self.apple, 1, 0), (self.banana, 2, 0)]
        self.assertCountEqual(move_format, expected_move_format)
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_some_products_have_no_weight(self):
        """
        Ensure when a product has no weight it is assumed as 0
        so will not contribute to a split.
        """
        self.apple.weight = 0

        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 5)
        apples_info = [{"product": self.apple, "uom_qty": 5}]
        bananas_info = [{"product": self.banana, "uom_qty": 5}]
        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check there are 2 pickings for 2 bananas, 1 picking for 1 banana, and 5 apples in one of those pickings.
        self.assertEqual(len(all_pickings), 3)
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        # NOTE: Is it deterministic that the apples always end up with the 1 banana?
        # Or could it end up in the picking for 2 bananas?
        self.assertCountEqual(quantities_per_pick, [6, 2, 2])

        # Check that one picking is for 2 bananas and 5 apples
        mixed_picking = all_pickings.filtered(lambda p: len(p.move_lines) == 2)
        self.assertEqual(len(mixed_picking), 1)
        self.assertCountEqual(
            mixed_picking.move_lines.mapped("product_id").ids, (self.apple + self.banana).ids
        )
        apple_line = mixed_picking.move_lines.filtered(lambda ml: ml.product_id == self.apple)
        self.assertEqual(apple_line.product_uom_qty, 5)
        banana_line = mixed_picking.move_lines.filtered(lambda ml: ml.product_id == self.banana)
        self.assertEqual(banana_line.product_uom_qty, 1)
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_product_weight_exceeds_max_1(self):
        """
        Ensure when a product exceeds the max weight as defined on
        u_assign_refactor_constraint_value it is split onto a pick on its own
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 5)
        self.create_quant(self.cherry.id, self.test_stock_location_03.id, 2)
        apples_info = [{"product": self.apple, "uom_qty": 5}]
        bananas_info = [{"product": self.banana, "uom_qty": 5}]
        cherries_info = [{"product": self.cherry, "uom_qty": 2}]

        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.create_move(self.picking, cherries_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check there are 2 pickings each for 2 bananas and 2 apples, a picking for 1 banana and 1 apple,
        # and 2 pickings for 1 cherry.
        self.assertEqual(len(all_pickings), 7)
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [2, 2, 2, 2, 2, 1, 1])

        for picking in all_pickings:
            if self.cherry in picking.move_lines.mapped("product_id"):
                self.assertEqual(len(picking.move_lines), 1)
                self.assertEqual(picking.move_lines.product_uom_qty, 1)
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_product_weight_exceeds_max_2(self):
        """
        Ensure when a product exceeds the max weight as defined on
        u_assign_refactor_constraint_value it is split onto multiple picks on their own
        """
        self.create_quant(self.cherry.id, self.test_stock_location_03.id, 3)
        cherries_info = [{"product": self.cherry, "uom_qty": 3}]
        self.create_move(self.picking, cherries_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        self.assertEqual(len(all_pickings), 3)
        # Check there are 3 pickings each for 1 cherry
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [1, 1, 1])
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_product_weight_exceeds_max_3(self):
        """
        Ensure when a product exceeds the max weight as defined on
        u_assign_refactor_constraint_value it is split onto multiple picks on their own,
        even if preceding moves do not exceed the max quantity
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 1)
        self.create_quant(self.cherry.id, self.test_stock_location_03.id, 3)
        apples_info = [{"product": self.apple, "uom_qty": 1}]
        cherries_info = [{"product": self.cherry, "uom_qty": 3}]
        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, cherries_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        self.assertEqual(len(all_pickings), 4)
        # Check there are 4 pickings, 1 for 1 apple, and 3 each for 1 cherry
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [1, 1, 1, 1])
        self.assert_weight_not_exceeded(all_pickings)

    def test_split_by_weight_does_not_exceed_max(self):
        """
        Ensure that when a product quantity on its own does not exceed the max, but multiple
        quantities of it would, that the moves are split before it exceeds the max
        """
        self.picking_type_pick.write(
            {
                "u_assign_refactor_constraint_value": 20,
            }
        )
        self.apple.weight = 8

        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        apples_info = [{"product": self.apple, "uom_qty": 5}]
        self.create_move(self.picking, apples_info)
        self.picking.action_confirm()

        all_pickings = self.Picking.search(self.pick_domain)

        self.assertEqual(len(all_pickings), 3)
        # Check there are 3 pickings, 2 for 2 apples each, and 1 for 1 apple
        quantities_per_pick = [
            sum(pick.move_lines.mapped("product_uom_qty")) for pick in all_pickings
        ]
        self.assertCountEqual(quantities_per_pick, [2, 2, 1])
        self.assert_weight_not_exceeded(all_pickings)


class TestRefactoringAssignSplittingWeight(RefactoringByWeightBase):
    """Tests splitting by maximum weight."""

    @classmethod
    def setUpClass(cls):
        """
        Split picking to maximum weight
        """
        super().setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.picking_type_pick.write(
            {
                "u_post_assign_action": "by_maximum_weight",
                "u_assign_refactor_constraint_value": 20,
            }
        )
        # Configure product weights.
        cls.apple.weight = 1
        cls.banana.weight = 10
        cls.cherry.weight = 30
        # Set 'Units' rounding to 1, because we don't want to allow transfers for anything under a unit.
        cls.apple.uom_id.rounding = 1

        cls.picking = cls.create_picking(cls.picking_type_pick)
        cls.pick_domain = [("picking_type_id", "=", cls.picking_type_pick.id)]
        """
        Delete me eventually. Helper for debugging qtys on the picks:

        for p in all_pickings:
            print(p.name)
            print("moves: ", [(x.product_id.name, x.product_id.weight, x.product_uom_qty) for x in p.move_lines])
            print("move lines: ", [(x.product_id.name, x.product_id.weight, x.product_uom_qty) for x in p.move_line_ids])
            print("")

        """

    def test_refactor_assign_all_available_no_refactor(self):
        """
        Ensure that when all stock is assigned to a pick, if the assigned stock
        is under the weight limit, that no refactoring occurrs.
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 1)
        apples_info = [{"product": self.apple, "uom_qty": 5}]
        bananas_info = [{"product": self.banana, "uom_qty": 1}]

        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.action_assign()

        all_pickings = self.Picking.search(self.pick_domain)
        # Check there is only 1 picking.
        self.assertEqual(len(all_pickings), 1)

        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(6, 6)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        self.assert_weight_not_exceeded(all_pickings)

    def test_refactor_assign_all_available_refactor(self):
        """
        Ensure that when all stock is assigned to a pick, if the assigned stock
        is over the weight limit, that the moves and lines are refactored together.
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 5)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 3)
        apples_info = [{"product": self.apple, "uom_qty": 5}]
        bananas_info = [{"product": self.banana, "uom_qty": 3}]

        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.action_assign()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check there are 2 pickings. One for 5 apples and 1 banana (15kg) and one for 2 bananas (20kg)
        self.assertEqual(len(all_pickings), 2)
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(6, 6), (2, 2)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        self.assert_weight_not_exceeded(all_pickings)

    def test_refactor_assign_not_all_available_refactor(self):
        """
        Ensure that when not all stock is assigned to a pick, if the assigned stock
        is over the weight limit, that the moves and lines are refactored together.
        Any stock that is not assigned is left as remainder
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 1)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 3)
        apples_info = [{"product": self.apple, "uom_qty": 5}]
        bananas_info = [{"product": self.banana, "uom_qty": 3}]

        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.action_assign()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check there are 3 pickings. One for 1 apple and 1 banana (11kg) one for 2 bananas (20kg)
        # and one unassigned for 4 apples (4kg)
        self.assertEqual(len(all_pickings), 3)
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(2, 2), (2, 2), (4, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        self.assert_weight_not_exceeded(all_pickings)

    def test_refactor_assign_not_all_available_refactor_2(self):
        """
        Ensure that when not all stock is assigned to a pick, if the assigned stock
        is over the weight limit, that the moves and lines are refactored together.
        Any stock that is not assigned is left as remainder
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 35)
        apples_info = [{"product": self.apple, "uom_qty": 38}]

        self.create_move(self.picking, apples_info)
        self.picking.action_assign()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check there are 3 pickings. One for 20 apples (20kg) one for 15 apples (15kg)
        # and one unassigned for 3 apples (3kg)
        self.assertEqual(len(all_pickings), 3)
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(20, 20), (15, 15), (3, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        self.assert_weight_not_exceeded(all_pickings)

    def test_refactor_assign_not_all_available_refactor_3(self):
        """
        Ensure that when not all stock is assigned to a pick, if the assigned stock
        is over the weight limit, that the moves and lines are refactored together.
        Any stock that is not assigned is left as remainder
        """
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 35)
        apples_info = [{"product": self.apple, "uom_qty": 38}]
        bananas_info = [{"product": self.banana, "uom_qty": 5}]

        self.create_move(self.picking, apples_info)
        self.create_move(self.picking, bananas_info)
        self.picking.action_assign()

        all_pickings = self.Picking.search(self.pick_domain)

        # Check there are 3 pickings. One for 20 apples (20kg) one for 15 apples (15kg)
        # and one unassigned for 3 apples and 5 bananas (53kg)
        self.assertEqual(len(all_pickings), 3)
        quantities_ordered_and_reserved = [
            (
                sum(pick.move_lines.mapped("product_uom_qty")),
                sum(pick.move_lines.mapped("reserved_availability")),
            )
            for pick in all_pickings
        ]
        expected_quantities_ordered_and_reserved = [(20, 20), (15, 15), (8, 0)]
        self.assertCountEqual(
            quantities_ordered_and_reserved, expected_quantities_ordered_and_reserved
        )
        self.assert_weight_not_exceeded(all_pickings.filtered(lambda p: p.state == "assigned"))
