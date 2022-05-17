import re

from .common import BaseUDES


class TestStockWarehouseModel(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockWarehouseModel, cls).setUpClass()
        cls.Warehouse = cls.env["stock.warehouse"]

    def test_can_find_expected_picking_type(self):
        """Test checks if the test picking types are present"""
        test_picking_types = self.warehouse.get_picking_types().filtered(
            lambda pt: "TEST" in pt.name
        )
        self.assertEqual(len(test_picking_types), 6)

    def test_finds_expected_number_of_picking_types(self):
        """Test checks if the test picking types and the normal pick types are present"""
        test_picking_types = self.warehouse.get_picking_types()
        self.assertEqual(len(test_picking_types), 9)

    def test_get_default_picking_types_new_warehouse(self):
        """Create a new warehouse and look at the default picking types"""
        # Create a new company creates a new warehouse
        test_company = self.create_company("test_company")
        new_warehouse = self.Warehouse.search([("company_id", "=", test_company.id)])
        test_picking_types = new_warehouse.get_picking_types()
        self.assertEqual(len(test_picking_types), 3)

    def test_check_picking_types_prefix_after_updating_warehouse_code(self):
        """
        Test that making changes to the warehouse does not cause the picking type prefixes to be reset.
        """
        goods_in = self.env.ref("stock.picking_type_in")
        goods_in_prefix = goods_in.sequence_id.prefix
        self.assertEqual(goods_in_prefix, "IN")

        self.warehouse.write({"code": "NEW_WAREHOUSE_CODE"})

        goods_in = self.env.ref("stock.picking_type_in")
        goods_in_prefix = goods_in.sequence_id.prefix
        self.assertEqual(goods_in_prefix, "IN")

        self.create_quant(self.apple.id, self.test_stock_location_01.id, 10)
        products_info = [{"product": self.apple, "uom_qty": 10}]
        picking = self.create_picking(
            picking_type=goods_in,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,
        )

        self.assertTrue(bool(re.fullmatch(r"IN\d{5}", picking.name)))
