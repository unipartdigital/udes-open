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
