from odoo.exceptions import ValidationError
from . import common
from ..registry.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY

class TestSuggestExactlyMatchMoveLine(common.SuggestedLocations):
    @classmethod
    def setUpClass(cls):
        super(TestSuggestExactlyMatchMoveLine, cls).setUpClass()
        policy_name = "exactly_match_move_line"
        cls.ByProduct = SUGGEST_LOCATION_REGISTRY[policy_name](cls.env)
        cls.picking_type_pick.u_suggest_locations_policy = policy_name

        cls.create_quant(cls.apple.id, cls.stock_location.id, 10)
        
        cls._pick_info = [{"product": cls.apple, "uom_qty": 5}]
    

    def test_correct_location_suggested_for_generic_location_destination(self):
        mls = self._generate_move_lines_for_picking_for_given_destination_location(self.out_location.id)

        self._check_move_lines_destination_location_match_expected_location(mls, self.out_location)


    def test_correct_location_suggested_for_view_location_destination(self):
        self.out_location.write({"usage": "view"})

        mls = self._generate_move_lines_for_picking_for_given_destination_location(self.out_location.id)

        self._check_move_lines_destination_location_match_expected_location(mls, self.out_location)


    def test_validate_location_dest_fails_for_given_destination_location(self):
        self.picking_type_pick.write({'u_drop_location_constraint': 'enforce'})

        mls = self._generate_move_lines_for_picking_for_given_destination_location(self.out_location.id)

        with self.assertRaises(ValidationError):
            mls.validate_location_dest(locations = self.test_received_location_01)

    
    def _check_move_lines_destination_location_match_expected_location(self, move_lines, expected_location):
        for move_line in move_lines:
            with self.subTest(move_line = move_line): 
                self.assertEqual(move_line.location_dest_id, expected_location)

    def _generate_move_lines_for_picking_for_given_destination_location(self, picking_dest_location):
        picking = self.create_picking(
            self.picking_type_pick, products_info=self._pick_info, confirm=True, assign=True, location_dest_id=picking_dest_location
        )
        return picking.move_line_ids