"""Unit tests for the StockPicking model."""
from . import common


class StockPickingGetInfoTestCase(common.BaseTestCase, common.GetInfoTestMixin):
    """Unit tests for the get_info method."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()
        stock_location = cls.env.ref("stock.stock_location_stock")
        src_location = cls.create_location("Stock01", location_id=stock_location.id)
        dest_location = cls.create_location("Stock02", location_id=stock_location.id)
        picking_type = cls.get_picking_type_by_name("Pack")
        apple = cls.create_product("Apple")
        cls.create_quant(apple.id, src_location.id, 1)
        products_info = [{"product": apple, "qty": 1}]
        vals = {
            "location_dest_id": dest_location.id,
            "location_id": src_location.id,
            "assign": True,
        }
        picking = cls.create_picking(picking_type, products_info, **vals)

        cls.object_under_test = picking

        cls.expected_keys = frozenset(
            [
                "display_name",
                "id",
                "location_dest_id",
                "move_line_ids",
                "name",
                "origin",
                "picking_type_id",
                "priority",
                "state",
            ]
        )
