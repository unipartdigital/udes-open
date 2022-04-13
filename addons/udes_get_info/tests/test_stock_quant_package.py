"""Unit tests for the StockQuantPackage model."""
from . import common


class StockQuantPackageGetInfoTestCase(common.BaseTestCase, common.GetInfoTestMixin):
    """Unit tests for the get_info method."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()
        stock_location = cls.env.ref("stock.stock_location_stock")
        cls.object_under_test = cls.create_package(location_id=stock_location.id)

        cls.expected_keys = frozenset(["id", "display_name", "name"])
