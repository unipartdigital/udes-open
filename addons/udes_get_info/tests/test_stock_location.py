"""Unit tests for the StockLocation model."""
from . import common


class StockLocationGetInfoTestCase(common.BaseTestCase, common.GetInfoTestMixin):
    """Unit tests for the get_info method."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()
        cls.object_under_test = cls.env.ref("stock.stock_location_stock")

        cls.expected_keys = frozenset(
            [
                "barcode",
                "complete_name",
                "display_name",
                "id",
                "name",
                "posx",
                "posy",
                "posz",
                "return_location",
                "scrap_location",
            ]
        )
