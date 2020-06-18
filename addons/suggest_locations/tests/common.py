# -*- coding: utf-8 -*-
from addons.udes_stock.tests import common


class SuggestedLocations(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(SuggestedLocations, cls).setUpClass()
        # Create extra locations
        Location = cls.env["stock.location"]
        cls.test_stock_location_03 = Location.create(
            {
                "name": "Test stock location 03",
                "barcode": "LSTEST03",
                "location_id": cls.stock_location.id,
            }
        )
        cls.test_goodsout_location_03, cls.test_goodsout_location_04 = Location.create(
            [
                {
                    "name": "Test Goods Out location 03",
                    "barcode": "LGOTEST03",
                    "location_id": cls.out_location.id,
                },
                {
                    "name": "Test Goods Out location 04",
                    "barcode": "LGOTEST04",
                    "location_id": cls.out_location.id,
                },
            ]
        )

        cls.test_trailer_location_03, cls.test_trailer_location_04 = Location.create(
            [
                {
                    "name": "Test Trailer location 03",
                    "barcode": "LTRAILERTEST03",
                    "location_id": cls.trailer_location.id,
                },
                {
                    "name": "Test Trailer location 04",
                    "barcode": "LTRAILERTEST04",
                    "location_id": cls.trailer_location.id,
                },
            ]
        )
