from odoo.addons.udes_stock.tests import common


class SuggestedLocations(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(SuggestedLocations, cls).setUpClass()
        # Create extra locations
        Location = cls.env["stock.location"]
        cls.test_check_location_03, cls.test_check_location_04 = Location.create(
            [
                {
                    "name": "Test Check location 03",
                    "barcode": "LCTEST03",
                    "location_id": cls.check_location.id,
                },
                {
                    "name": "Test Check location 04",
                    "barcode": "LCTEST04",
                    "location_id": cls.check_location.id,
                },
            ]
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
    
    def _check_move_lines_destination_location_match_expected_location(
        self, move_lines, expected_location
    ):
        for move_line in move_lines:
            with self.subTest(move_line=move_line):
                self.assertEqual(move_line.location_dest_id, expected_location)

    def _generate_move_lines_for_picking_for_given_destination_location(
        self, picking_dest_location
    ):
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self._pick_info,
            assign=True,
            location_dest_id=picking_dest_location,
        )
        return picking.move_line_ids
