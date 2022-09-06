from odoo.exceptions import ValidationError
from . import common
from ..registry.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY


class TestSuggestByEmptyLocation(common.SuggestedLocations):
    @classmethod
    def setUpClass(cls):
        super(TestSuggestByEmptyLocation, cls).setUpClass()
        policy_name = "by_empty_location"
        cls.ByProduct = SUGGEST_LOCATION_REGISTRY[policy_name](cls.env)
        cls.picking_type_pick.u_suggest_locations_policy = policy_name

        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)

        cls._pick_info = [{"product": cls.apple, "uom_qty": 5}]

    def _create_one_non_empty_child_location_for_given_location(self, parent_location):
        Location = self.env["stock.location"]

        child_location_with_quant = Location.create(
            {
                "name": "child_loc_with_quant",
                "location_id": parent_location.id,
                "barcode": "childlocation",
            }
        )

        self.create_quant(self.banana.id, child_location_with_quant.id, 5)

    def test_correct_location_suggested_when_empty_child_location_is_available(self):
        mls = self._generate_move_lines_for_picking_for_given_destination_location(
            self.test_goodsout_location_01.id
        )

        self._check_move_lines_destination_location_match_expected_location(
            mls, self.test_goodsout_location_01
        )

    def test_correct_location_suggested_when_no_empty_child_location_is_available(self):
        mls = self._generate_move_lines_for_picking_for_given_destination_location(
            self.test_goodsout_location_02.id
        )

        self._check_move_lines_destination_location_match_expected_location(
            mls, self.test_goodsout_location_02
        )

    def test_correct_location_suggested_when_empty_child_location_but_no_barcode(self):
        # These are all children of out_location
        self.test_goodsout_location_01.write({"barcode": False})
        self.test_goodsout_location_02.write({"barcode": False})
        self.test_goodsout_location_03.write({"barcode": False})
        self.test_goodsout_location_04.write({"barcode": False})

        mls = self._generate_move_lines_for_picking_for_given_destination_location(
            self.out_location.id
        )

        self._check_move_lines_destination_location_match_expected_location(mls, self.out_location)

    def test_correct_location_suggested_when_child_location_but_not_empty(self):
        test_location = self.create_location(name="Test Suggest Location", usage="view")
        self._create_one_non_empty_child_location_for_given_location(test_location)

        mls = self._generate_move_lines_for_picking_for_given_destination_location(test_location.id)

        self._check_move_lines_destination_location_match_expected_location(mls, test_location)

    def test_validate_location_dest_fails_when_bad_location_is_passed(self):
        self.picking_type_pick.write({"u_drop_location_constraint": "enforce"})

        mls = self._generate_move_lines_for_picking_for_given_destination_location(
            self.out_location.id
        )

        with self.assertRaises(ValidationError):
            mls.validate_location_dest(locations=self.test_received_location_01)
