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
        Test that making changes to the warehouse does not cause the pickingtype prefixes to be reset. 
        """ 
        Pickingtype = self.env["stock.picking.type"]
        
        goods_in_prefix = Pickingtype.search([("name", "=", "Goods In")]).sequence_id.prefix
        self.assertEqual(goods_in_prefix, "IN")
        
        self.warehouse.write({"code":"NEW_WAREHOUSE_CODE"})

        goods_in_prefix = Pickingtype.search([("name", "=", "Goods In")]).sequence_id.prefix
        self.assertEqual(goods_in_prefix, "IN")

