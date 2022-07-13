"""Unit tests for the StockQuant model."""
from . import common


class StockQuantGetInfoTestCase(common.BaseTestCase, common.GetInfoTestMixin):
    """Unit tests for the get_info method."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()
        stock_location = cls.env.ref("stock.stock_location_stock")
        location = cls.create_location("Stock01", location_id=stock_location.id)
        product = cls.create_product("apple")
        package = cls.create_package()
        cls.object_under_test = cls.create_quant(
            product_id=product.id,
            location_id=location.id,
            qty=10,
            package_id=package.id,
            available_quantity=5,
            reserved_quantity=5,
        )

        cls.expected_keys = frozenset(
            [
                "available_quantity",
                "display_name",
                "id",
                "location_id",
                "package_id",
                "product_id",
                "quantity",
                "lot_id",
                "reserved_quantity",
            ]
        )
