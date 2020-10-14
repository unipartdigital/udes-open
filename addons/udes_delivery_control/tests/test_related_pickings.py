from odoo.addons.udes_delivery_control.tests import common


class TestRelatedPickings(common.TestDeliveryControl):
    @classmethod
    def setUpClass(cls):
        super(TestRelatedPickings, cls).setUpClass()

        # Complete Delivery Control picking
        cls.delivery_control_picking.action_confirm()
        cls.delivery_control_picking.action_done()

        cls.goods_in_picking = cls.delivery_control_picking.u_goods_in_picking_id
        cls.goods_in_picking.name = "GI Pick"

    def _assert_picking_related_pickings_match_expected_values(self, pickings, expected_values):
        """
        Assert that each supplied picking returns the expected related picking records

        :args:
                - pickings: A recordset of pickings
                - expected_values: A dictionary with field names to check as keys
                                   Each value should be another dictionary with the picking as key, 
                                   and expected pickings (or False for none) to return as value
        """
        for picking in pickings:
            # Loop through all fields that need to be checked
            for field in expected_values.keys():
                returned_picks = picking[field]
                expected_picks = expected_values[field][picking]

                if not expected_picks:
                    # Assert that the field returns an empty recordset
                    self.assertFalse(
                        returned_picks, f"{picking.name} should not have any pickings for '{field}'"
                    )
                else:
                    # Assert that the recordset only contains the expected picks
                    expected_pick_names = expected_picks.mapped("name")

                    self.assertEqual(
                        returned_picks,
                        expected_picks,
                        f"'{field}' for {picking.name} should be '{expected_pick_names}'",
                    )

    def test_assert_delivery_control_goods_in_relationship(self):
        """
        Assert that the first/previous/next picking fields are computed correctly

        Delivery Control should be the first picking and before the Goods In picking
        """
        expected_pickings_by_field = {
            "u_first_picking_ids": {
                self.delivery_control_picking: self.delivery_control_picking,
                self.goods_in_picking: self.delivery_control_picking,
            },
            "u_prev_picking_ids": {
                self.delivery_control_picking: False,
                self.goods_in_picking: self.delivery_control_picking,
            },
            "u_next_picking_ids": {
                self.delivery_control_picking: self.goods_in_picking,
                self.goods_in_picking: False
            },
        }

        picks = self.delivery_control_picking | self.goods_in_picking

        # Assert that each computed picking field returns the expected result for all picks
        self._assert_picking_related_pickings_match_expected_values(
            picks, expected_pickings_by_field
        )

    def test_assert_related_pickings_computed_correctly_with_additional_pickings(self):
        """
        Assert that the first/previous/next picking fields are computed correctly
        with the following setup in addition to the Delivery Control and Goods In picking:

        3 picks (A, B and C):

        - Pick A - direct parent of Pick C
        - Pick B - originates from Goods In Pick
        - Pick C - originates from Goods In Pick and Pick A
        """
        # Create extra picks
        pick_a = self.create_picking(self.picking_type_pick, name="Pick A")
        pick_b = self.create_picking(self.picking_type_pick, name="Pick B")
        pick_c = self.create_picking(self.picking_type_pick, name="Pick C")

        # Create moves for Goods In and extra picks
        goods_in_move = self.create_move(self.apple, 1, self.goods_in_picking)
        pick_a_move = self.create_move(self.apple, 1, pick_a)
        pick_b_move = self.create_move(self.apple, 1, pick_b)
        pick_c_move = self.create_move(self.apple, 1, pick_c)

        # Set Pick B's move to have originated from Goods In's move
        pick_b_move.move_orig_ids = goods_in_move

        # Set Pick C's move to have originated from Goods In and Pick A's move
        pick_c_move.move_orig_ids = goods_in_move | pick_a_move

        # Pick Relationship Diagram
        #
        # DC        A
        # |        /
        # GI____  /
        # |     \/
        # B     C
        #
        # Expected Results from Computed Fields
        #
        # Pick A:
        #   -- First: Pick A (A doesn't originate from any pick)
        #   -- Prev:  False (A doesn't originate from any pick)
        #   -- Next:  Pick C (C originates from A)
        #
        # Pick B:
        #   -- First: Pick DC (B originates from GI, and GI originates from DC)
        #   -- Prev:  Pick GI (B originates from GI)
        #   -- Next:  False (No picks originate from B)
        #
        # Pick C:
        #   -- First: Pick DC and A (C originates from A and GI, and GI originates from DC)
        #   -- Prev:  Pick GI and A (C originates from A and GI)
        #   -- Next:  False (No picks originate from C)

        expected_pickings_by_field = {
            "u_first_picking_ids": {
                self.delivery_control_picking: self.delivery_control_picking,
                self.goods_in_picking: self.delivery_control_picking,
                pick_a: pick_a,
                pick_b: self.delivery_control_picking,
                pick_c: self.delivery_control_picking | pick_a,
            },
            "u_prev_picking_ids": {
                self.delivery_control_picking: False,
                self.goods_in_picking: self.delivery_control_picking,
                pick_a: False,
                pick_b: self.goods_in_picking,
                pick_c: self.goods_in_picking | pick_a,
            },
            "u_next_picking_ids": {
                self.delivery_control_picking: self.goods_in_picking,
                self.goods_in_picking: pick_b | pick_c,
                pick_a: pick_c,
                pick_b: False,
                pick_c: False,
            },
        }

        picks = self.delivery_control_picking | self.goods_in_picking | pick_a | pick_b | pick_c

        # Assert that each computed picking field returns the expected result for all picks
        self._assert_picking_related_pickings_match_expected_values(
            picks, expected_pickings_by_field
        )

