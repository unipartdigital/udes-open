from .common import BaseUDES


class TestStockWarehouseModel(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockWarehouseModel, cls).setUpClass()
        cls.Warehouse = cls.env["stock.warehouse"]

    def test01_get_test_picking_types(self):
        """Test checks if the test picking types are present"""
        test_picking_types = self.warehouse.get_picking_types().filtered(
            lambda pt: "TEST" in pt.name
        )
        self.assertEqual(len(test_picking_types), 6)

    def test02_get_picking_types(self):
        """Test checks if the test picking types and the normal pick types are present"""
        test_picking_types = self.warehouse.get_picking_types()
        self.assertEqual(len(test_picking_types), 12)

    def test03_get_default_picking_types_new_warehouse(self):
        """Create a new warehouse and look at the default picking types"""
        # Create a new company creates a new warehouse
        test_company = self.create_company("test_company")
        new_warehouse = self.Warehouse.search([("company_id", "=", test_company.id)])
        test_picking_types = new_warehouse.get_picking_types()
        self.assertEqual(len(test_picking_types), 3)
