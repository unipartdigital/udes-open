# -*- coding: utf-8 -*-
from .common import BaseUDES


class TestStockQuantModel(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockQuantModel, cls).setUpClass()
        cls.Quant = cls.env["stock.quant"]
        cls.test_package = cls.create_package()
        cls.test_package2 = cls.create_package()
        cls.quantA = cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 10, package_id=cls.test_package.id,
        )
        cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 5, package_id=cls.test_package.id
        )

        cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 1, package_id=cls.test_package.id
        )

        cls.create_quant(
            cls.banana.id, cls.test_stock_location_01.id, 10, package_id=cls.test_package.id
        )

        cls.create_quant(
            cls.banana.id, cls.test_stock_location_02.id, 10, package_id=cls.test_package2.id
        )
        # Total Apples = 11
        # reserved = 0
        # Total Bananas = 20
        # reserved = 0

        # Create dummy user
        cls.test_user = cls.create_user("test_user", "test_user_login")

    def test01_get_quantity(self):
        """ Test get_quantity """
        self.assertEqual(self.test_stock_location_01.quant_ids.get_quantity(), 26)

    def test02_get_quantities_by_key(self):
        """ Test get_quantities_by_key """
        self.assertEqual(
            {self.apple: 16, self.banana: 10},
            self.test_stock_location_01.quant_ids.get_quantities_by_key(),
        )
        # group by non-product_ids: test name
        self.assertEqual(
            {self.apple.name: 16, self.banana.name: 10},
            self.test_stock_location_01.quant_ids.get_quantities_by_key(
                get_key=lambda q: q.product_id.name
            ),
        )
        # Group by name, and only available (not-reserved) quantities
        # Still should return 16 and 10
        self.assertEqual(
            {self.apple.name: 16, self.banana.name: 10},
            self.test_stock_location_01.quant_ids.get_quantities_by_key(
                get_key=lambda q: q.product_id.name, only_available=True
            ),
        )
        # Reserve 5 apples
        self.quantA.reserved_quantity = 5
        # Group by name, and only available (not-reserved) quantities
        self.assertEqual(
            {self.apple.name: 11, self.banana.name: 10},
            self.test_stock_location_01.quant_ids.get_quantities_by_key(
                get_key=lambda q: q.product_id.name, only_available=True
            ),
        )

    def test03_gather_success(self):
        """ Test extended _gather function """
        gathered_items = self.Quant._gather(self.apple, self.test_stock_location_01)
        # Check the number of apple quants returned is correct
        self.assertEqual(len(gathered_items), 3)
        # Check that the products are all of expected type
        self.assertEqual(gathered_items.product_id, self.apple)

        # Unfold the returned quants
        _q1, second_quant, _q2 = gathered_items
        # Check when quant_ids is set in the context
        gathered_items_subset = self.Quant.with_context(quant_ids=[second_quant.id])._gather(
            self.apple, self.test_stock_location_01
        )
        self.assertEqual(len(gathered_items_subset), 1)
        self.assertEqual(gathered_items_subset.product_id, self.apple)
        self.assertEqual(gathered_items_subset, second_quant)

    def test04_gather_location_no_product(self):
        """ Test extended _gather function on a location without apples """
        gathered_items = self.Quant._gather(self.apple, self.test_stock_location_02)
        # Check the number of apple quants returned is correct
        self.assertFalse(len(gathered_items))

    def test05_create_picking_from_single_quant(self):
        """ Create a picking from a single quant """
        pick = self.quantA.create_picking(self.picking_type_pick)
        # Confirm made in state draft
        self.assertEqual(pick.state, "draft")
        # Confirm default location used if non specified
        self.assertEqual(pick.location_id, self.picking_type_pick.default_location_src_id)
        # Confirm default dest location used if non specified
        self.assertEqual(pick.location_dest_id, self.picking_type_pick.default_location_dest_id)
        # Confirm correct picking type id associated
        self.assertEqual(pick.picking_type_id, self.picking_type_pick)
        # Check default priority is 1 = 'Normal'
        self.assertEqual(pick.priority, "1")
        #  Check picking has correct products associated to it
        self.assertEqual(pick.product_id, self.apple)
        #  Check picking has correct quantities associated to it
        self.assertEqual(pick.move_lines.product_id, self.apple)
        self.assertEqual(pick.move_lines.product_qty, 10)

    def test06_create_picking_from_single_quant_confirm(self):
        """ Create a picking from a single quant and confirm """
        pick = self.quantA.create_picking(self.picking_type_pick, confirm=True)
        # Check it is confirmed
        self.assertEqual(pick.state, "confirmed")

    def test07_create_picking_from_single_quant_assign(self):
        """ Create a picking from a single quant and assign to user """
        pick = self.quantA.create_picking(
            self.picking_type_pick, assign=True, user_id=self.test_user.id
        )
        # Check it is in state assigned
        self.assertEqual(pick.state, "assigned")
        # Check user is assigned
        self.assertEqual(pick.user_id, self.test_user)
        # Check QuantA is now reserved
        self.assertEqual(self.quantA.reserved_quantity, 10)

    def test08_create_picking_from_single_quant_priority(self):
        """ Create a picking from a single quant
            Change the priority to Urgent
            Priorities: [('0', 'Not urgent'), ('1', 'Normal'), ('2', 'Urgent'), ('3', 'Very Urgent')]
        """
        pick = self.quantA.create_picking(self.picking_type_pick, priority="2")
        # Check priority is 2 = 'Urgent'
        self.assertEqual(pick.priority, "2")

    def test09_create_picking_from_single_quant_non_default_locations(self):
        """ Create a picking from a single quant
            - non-default location_id
            - non-default location_dest_id
        """
        pick = self.quantA.create_picking(
            self.picking_type_pick,
            location_id=self.test_stock_location_01.id,
            location_dest_id=self.test_goodsout_location_02.id,
        )
        # Confirm default location used if non specified
        self.assertEqual(pick.location_id, self.test_stock_location_01)
        self.assertNotEqual(pick.location_id, self.picking_type_pick.default_location_src_id)
        # Confirm default dest location used if non specified
        self.assertEqual(pick.location_dest_id, self.test_goodsout_location_02)
        self.assertNotEqual(pick.location_id, self.picking_type_pick.default_location_dest_id)

    def test10_create_picking_from_multiple_quants(self):
        """ Multiple quants for pick """
        # Get all quants in test package
        quants = self.test_package._get_contained_quants()
        pick = quants.create_picking(self.picking_type_pick)
        #  Check picking has correct products and quantities associated to it
        self.assertEqual(pick.move_lines.product_id, quants.product_id)
        self.assertEqual(pick.move_lines.mapped("product_qty"), [16.0, 10.0])
