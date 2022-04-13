"""Unit tests for the StockMoveLine model."""
from . import common


class StockMoveLineGetInfoTestCase(common.BaseTestCase, common.GetInfoTestMixin):
    """Unit tests for the get_info method."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()
        stock_location = cls.env.ref("stock.stock_location_stock")
        src_location = cls.create_location("Stock01", location_id=stock_location.id)
        dest_location = cls.create_location("Stock02", location_id=stock_location.id)
        picking_type = cls.get_picking_type_by_name("Pack")
        apple = cls.create_product("Apple")
        package = cls.create_package()
        cls.create_quant(
            apple.id, src_location.id, 1, package_id=package.id, serial_number="LOT001"
        )
        products_info = [{"product": apple, "qty": 1}]
        vals = {
            "location_dest_id": dest_location.id,
            "location_id": src_location.id,
            "assign": True,
        }
        picking = cls.create_picking(picking_type, products_info, **vals)
        picking.move_line_ids[0].qty_done = 1
        picking._action_done()

        cls.object_under_test = picking.move_line_ids

        # TODO conditional values
        cls.expected_keys = frozenset(
            [
                "create_date",
                "display_name",
                "id",
                "location_dest_id",
                "location_id",
                "lot_id",
                "package_id",
                "product_uom_qty",
                "qty_done",
                "result_package_id",
                "write_date",
            ]
        )
