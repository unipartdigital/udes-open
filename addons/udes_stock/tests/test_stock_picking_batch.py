from . import common


class TestStockPickingBatchCommon(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPickingBatchCommon, cls).setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.Location = cls.env["stock.location"]
        products_info = [{"product": cls.apple, "uom_qty": 10}]
        cls.test_picking_in = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=products_info,
            confirm=True,
            location_dest_id=cls.test_received_location_01.id,
            create_batch=True,
        )
        cls.test_picking_pick = cls.create_picking(
            cls.picking_type_pick, products_info=products_info, confirm=True
        )

    def test__create_backorder_picking_no_preserve_batch(self):
        self.assertEqual(len(self.test_picking_in.batch_id), 1)
        backorder = self.test_picking_in._create_backorder_picking(self.test_picking_in.move_lines)
        self.assertEqual(len(backorder.batch_id), 0)

    def test__create_backorder_picking_preserve_batch(self):
        self.picking_type_goods_in.u_preserve_backorder_batch = True
        self.assertEqual(len(self.test_picking_in.batch_id), 1)
        backorder = self.test_picking_in._create_backorder_picking(self.test_picking_in.move_lines)
        self.assertEqual(len(backorder.batch_id), 1)
        self.assertEqual(self.test_picking_in.batch_id, backorder.batch_id)
