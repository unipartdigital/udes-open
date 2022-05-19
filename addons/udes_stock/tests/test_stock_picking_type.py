import re

from . import common


class TestStockPickingType(common.BaseUDES):
    def test_writing_to_picking_type_does_reset_prefix_to_Odoo_style(self):
        Pickingtype = self.env["stock.picking.type"]

        goods_out = self.env.ref("stock.picking_type_out")
        goods_out_prefix = goods_out.sequence_id.prefix
        self.assertEqual(goods_out_prefix, "OUT")

        goods_out.write({"name": "Changed goods out", "sequence_code": "out"})

        goods_out = self.env.ref("stock.picking_type_out")
        goods_out_prefix = goods_out.sequence_id.prefix

        self.assertEqual(goods_out_prefix, "OUT")

        self.create_quant(self.apple.id, self.test_stock_location_01.id, 10)
        products_info = [{"product": self.apple, "uom_qty": 10}]
        picking = self.create_picking(
            picking_type=goods_out,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,
        )

        self.assertTrue(bool(re.fullmatch(r"OUT\d{5}", picking.name)))

    def test_create_new_picking_type_with_same_name_as_other_picking_and_no_sequence_id_attached(
        self,
    ):
        """
        Creating a new picking type the same name as an existing picking type, but with no sequence_id 
        attached. The new picking type will have the same prefix as the old picking type. 
        """
        Pickingtype = self.env["stock.picking.type"]

        old_goods_in = self.env.ref("stock.picking_type_in")
        old_goods_in_prefix = old_goods_in.sequence_id.prefix

        default_warehouse = self.env.ref("stock.warehouse0")

        new_goods_in = Pickingtype.create(
            {
                "name": "Goods In",
                "code": "incoming",
                "warehouse_id": default_warehouse.id,
                "company_id": default_warehouse.company_id.id,
            }
        )
        new_goods_in_prefix = new_goods_in.sequence_id.prefix

        self.assertEqual(new_goods_in_prefix, old_goods_in_prefix)

    def test_create_new_picking_type_with_same_name_as_other_picking_and_sequence_id_attached(self):
        """
        Creating a new picking type with the same name as an existing picking type, but with a new
        sequence_id attached. The new picking type will have the new sequence_id prefix.  
        """
        Pickingtype = self.env["stock.picking.type"]

        default_warehouse = self.env.ref("stock.warehouse0")

        goods_out = self.env.ref("stock.picking_type_out")
        goods_out_sequence = goods_out.sequence_id
        goods_out_prefix = goods_out_sequence.prefix

        new_goods_in = Pickingtype.create(
            {
                "name": "Goods In",
                "code": "incoming",
                "warehouse_id": default_warehouse.id,
                "company_id": default_warehouse.company_id.id,
                "sequence_id": goods_out_sequence.id,
            }
        )
        new_goods_in_prefix = new_goods_in.sequence_id.prefix

        self.assertEqual(new_goods_in_prefix, goods_out_prefix)

    def test_creating_new_warehouse_and_check_prefixes_on_default_picking_types(self):
        """
        Creating a new warehouse creates new picking types by default, these will have Odoo style prefixes. 
        """
        Pickingtype = self.env["stock.picking.type"]
        Warehouse = self.env["stock.warehouse"]

        second_warehouse = Warehouse.create(
            {
                "name": "Second Warehouse",
                "code": "WH2",
            }
        )

        second_warehouse_picking_types = Pickingtype.search(
            [("warehouse_id", "=", second_warehouse.id)]
        )

        for picking_type in second_warehouse_picking_types:
            with self.subTest(picking_type=picking_type):
                string_to_match = f'WH2\/{picking_type.name.upper().replace(" ", "_")}\/'
                self.assertTrue(
                    bool(re.fullmatch(string_to_match, picking_type.sequence_id.prefix))
                )

    def test_create_picking_type_with_same_name_as_one_already_stored_for_new_warehouse(self):
        """
        If there is a new warehouse, creating a picking type (for the new warehouse) with the same name as a picking
        type that already exists, and not specifying the sequence_id, will create a new picking type with a
        prefix that matches the one already stored. 
        """
        Pickingtype = self.env["stock.picking.type"]
        Warehouse = self.env["stock.warehouse"]

        old_goods_in = self.env.ref("stock.picking_type_in")
        old_goods_in_prefix = old_goods_in.sequence_id.prefix

        second_warehouse = Warehouse.create(
            {
                "name": "Second Warehouse",
                "code": "WH2",
            }
        )

        new_goods_in = Pickingtype.create(
            {
                "name": "Goods In",
                "code": "incoming",
                "warehouse_id": second_warehouse.id,
                "company_id": second_warehouse.company_id.id,
            }
        )
        new_goods_in_prefix = new_goods_in.sequence_id.prefix

        self.assertEqual(old_goods_in_prefix, new_goods_in_prefix)

    def test_creating_new_company_and_check_prefixes_on_picking_types_of_new_warehouse(self):
        """
        When creating a new company with a new warehouse, by default the new picking types should have an Odoo style 
        prefix. 
        """
        Pickingtype = self.env["stock.picking.type"]
        Company = self.env["res.company"]
        Warehouse = self.env["stock.warehouse"]

        new_company = Company.create({"name": "New Company"})

        new_warehouse = Warehouse.search([("company_id", "=", new_company.id)], limit=1)

        new_warehouse_picking_types = Pickingtype.search([("warehouse_id", "=", new_warehouse.id)])

        for picking_type in new_warehouse_picking_types:
            with self.subTest(picking_type=picking_type):
                string_to_match = f'New C\/{picking_type.name.upper().replace(" ", "_")}\/'
                self.assertTrue(
                    bool(re.fullmatch(string_to_match, picking_type.sequence_id.prefix))
                )
    
    def test_creating_new_company_and_create_for_new_company_new_warehouse(self):
        """
        If there is a new company created with a new warehouse, creating a picking type with same name as
        a picking type that already exists, and not specifying the sequence id, will create a new picking type with
        an Odoo style prefix. 
        """
        Pickingtype = self.env["stock.picking.type"]
        Company = self.env["res.company"]
        Warehouse = self.env["stock.warehouse"]

        new_company = Company.create({"name": "New Company"})

        new_warehouse = Warehouse.search([("company_id", "=", new_company.id)], limit=1)

        new_goods_in = Pickingtype.create(
            {
                "name": "Goods In",
                "code": "incoming",
                "warehouse_id": new_warehouse.id,
                "company_id": new_company.id,
            }
        )
        new_goods_in_prefix = new_goods_in.sequence_id.prefix

        string_to_match = f'New C\/{new_goods_in.name.upper().replace(" ", "_")}\/'
        self.assertTrue(
                    bool(re.fullmatch(string_to_match, new_goods_in_prefix))
        )
    
