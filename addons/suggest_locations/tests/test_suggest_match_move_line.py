# -*- coding: utf-8 -*-
from . import common
from ..models.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY


class TestSuggestMatchMoveLine(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestSuggestMatchMoveLine, cls).setUpClass()
        # Get class - is there a better way
        cls.MATCHML = SUGGEST_LOCATION_REGISTRY["match_move_line"](cls.env, False)
        cls.picking_type_pick.u_suggest_locations_policy = "match_move_line"
        # Create quants
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 2)
        cls.create_quant(cls.apple.id, cls.test_stock_location_02.id, 3)
        cls.create_quant(cls.banana.id, cls.test_stock_location_03.id, 10)
        # Create picking
        cls._pick_info = [{"product": cls.banana, "qty": 5}, {"product": cls.apple, "qty": 4}]
        cls.picking = cls.create_picking(
            cls.picking_type_pick, products_info=cls._pick_info, confirm=True, assign=True
        )
        cls.mls = cls.picking.move_line_ids

    def test01_get_values_from_mls(self):
        """ Get the destination location from move lines """
        vals = self.MATCHML.get_values_from_mls(self.mls)
        self.assertEqual(vals.get("location"), self.out_location)

    def test02_get_values_from_mls_failure(self):
        """ Fail to get details due to multilpe move lines given with differing destinations """
        # Change one of the destination locations
        self.mls.filtered(lambda ml: ml.product_id == self.banana).write(
            {"location_dest_id": self.test_goodsout_location_01.id}
        )
        with self.assertRaises(ValueError) as e:
            self.MATCHML.get_values_from_mls(self.mls)
        self.assertEqual(str(e.exception), f"Expected singleton: {self.mls.location_dest_id}")

    def test03_get_values_from_dict(self):
        """ Check that the location is returned from the dictionary correctly """
        #  Dictionary does not have picking_od
        with self.assertRaises(ValueError) as e:
            self.MATCHML.get_values_from_dict({"location_dest": self.test_goodsout_location_01.id})
        self.assertEqual(str(e.exception), "No picking found")
        #  Dictionary does not have location_dest_id
        with self.assertRaises(ValueError) as e:
            self.MATCHML.get_values_from_dict(
                {"picking_id": self.picking.id, "location_dest": self.test_goodsout_location_01.id}
            )
        self.assertEqual(str(e.exception), "No location found")
        # Successful picking found via integer
        values1 = self.MATCHML.get_values_from_dict(
            {"picking_id": self.picking.id, "location_dest_id": self.test_goodsout_location_01.id,}
        )
        # Expected result
        result = {
            "picking_id": self.picking,
            "location": self.test_goodsout_location_01,
        }
        self.assertEqual(values1, result)
        # Successful picking found via record
        values2 = self.MATCHML.get_values_from_dict(
            {"picking_id": self.picking.id, "location_dest_id": self.test_goodsout_location_01.id,}
        )
        self.assertEqual(values2, result)
