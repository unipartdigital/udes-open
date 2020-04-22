# -*- coding: utf-8 -*-
from .common import BaseUDES


class TestStockQuantModel(BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestStockQuantModel, cls).setUpClass()
        cls.Quant = cls.env['stock.quant']
        cls.test_package = cls.create_package()
        cls.test_package2 = cls.create_package()
        cls.quantA = cls.create_quant(
            cls.apple.id,
            cls.test_stock_location_01.id,
            10,
            package_id=cls.test_package.id,
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
        cls.test_user = cls.create_user('test_user', 'test_user_login')

    def test00_get_quantity(self):
        """ Test get_quantity """
        self.assertEqual(self.test_stock_location_01.quant_ids.get_quantity(), 26)

    def test01_get_quantities_by_key(self):
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

    def test_02_gather_success(self):
        """ Test extended _gather function """
        gathered_items = self.Quant._gather(self.apple, self.test_stock_location_01)
        # Check the number of apple quants returned is correct
        self.assertEqual(len(gathered_items), 3)
        # Check that the products are all of expected type
        self.assertEqual(gathered_items.product_id, self.apple)

        # Unfold the returned quants
        _q1, second_quant, _q2 = gathered_items
        # Check when quant_ids is set in the context
        gathered_items_subset = self.Quant.with_context(quant_ids=[second_quant.id])._gather(self.apple, self.test_stock_location_01)
        self.assertEqual(len(gathered_items_subset), 1)
        self.assertEqual(gathered_items_subset.product_id, self.apple)
        self.assertEqual(gathered_items_subset, second_quant)

    def test_03_gather_location_no_product(self):
        """ Test extended _gather function on a location without apples """
        gathered_items = self.Quant._gather(self.apple, self.test_stock_location_02)
        # Check the number of apple quants returned is correct
        self.assertFalse(len(gathered_items))
