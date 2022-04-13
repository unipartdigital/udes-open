"""Unit tests for the StockPickingType model."""
from . import common


class PickingTypeGetInfoTestCase(common.BaseTestCase, common.GetInfoTestMixin):
    """Unit tests for the get_info method."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()

        # Use Pack because it has a destination location set.
        cls.object_under_test = cls.get_picking_type_by_name("Pack")

        cls.expected_keys = frozenset(
            [
                "code",
                "company_id",
                "count_picking_ready",
                "default_location_dest_id",
                "default_location_src_id",
                "display_name",
                "id",
                "name",
                "sequence",
                "warehouse_id",
            ]
        )
