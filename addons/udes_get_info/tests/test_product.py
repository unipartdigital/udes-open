"""Unit tests for the Product model."""
from . import common


class ProductGetInfoTestCase(common.BaseTestCase, common.GetInfoTestMixin):
    """Unit tests for the get_info method."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()
        cls.object_under_test = cls.create_product("Apple")

        cls.expected_keys = frozenset(["id", "barcode", "display_name", "name", "tracking"])
