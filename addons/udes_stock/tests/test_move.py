"""Tests for the udes_stock.move model."""
# pylint: disable=protected-access
from . import common


class TestActionCancel(common.BaseUDES):
    """Tests for the Move._action_cancel method."""

    def setUp(self):
        super(TestActionCancel, self).setUp()

        # Create some locations.
        self.stock_location1 = self.env["stock.location"].create(
            {"name": "Location A", "location_id": self.stock_location.id}
        )
        self.stock_location2 = self.env["stock.location"].create(
            {"name": "Location B", "location_id": self.stock_location.id}
        )
        self.stock_location3 = self.env["stock.location"].create(
            {"name": "Location C", "location_id": self.stock_location.id}
        )

        # Make some stock.
        self.env["stock.quant"]._update_available_quantity(self.apple, self.stock_location1, 150.0)

        # Set up two related moves.
        self.move1 = self.env["stock.move"].create(
            {
                "name": "test_move_1",
                "location_id": self.stock_location1.id,
                "location_dest_id": self.stock_location2.id,
                "product_id": self.apple.id,
                "product_uom": self.apple.uom_id.id,
                "product_uom_qty": 10.0,
                "picking_type_id": self.env.ref("stock.picking_type_internal").id,
            }
        )
        self.move2 = self.env["stock.move"].create(
            {
                "name": "test_move_2",
                "location_id": self.stock_location2.id,
                "location_dest_id": self.stock_location3.id,
                "product_id": self.apple.id,
                "product_uom": self.apple.uom_id.id,
                "product_uom_qty": 10.0,
                "picking_type_id": self.env.ref("stock.picking_type_internal").id,
            }
        )
        self.move1.write({"move_dest_ids": [(4, self.move2.id, False)]})

        # Confirm and assign both moves.
        self.move1._action_confirm()
        self.move2._action_confirm()
        self.move1._action_assign()

    def test01_cancel_backorder_does_not_cancel_remaining(self):
        """Check that when a move is cancelled and its siblings are all cancelled/done
        but the move does not contain all of the qty (i.e. it is a backorder from a
        partially completed move), the remaining moves are not cancelled.
        """
        # Do half of move1 and cancel the backorder.
        self.move1._set_quantity_done(5)
        self.move1._action_done()
        new_move = self.move2.move_orig_ids - self.move1
        new_move._action_cancel()

        # move2 should still be assigned.
        self.assertEqual(self.move2.state, "assigned")
        self.assertEqual(self.move2.product_uom_qty, 5)

    def test02_cancel_order_cancels_remaining(self):
        """Check that when a move is cancelled and its siblings are all cancelled/done
        and the move contains all of the qty the remaining moves are cancelled.
        """
        # Cancel the whole of move1.
        self.move1._action_cancel()

        # move2 should also be cancelled.
        self.assertEqual(self.move2.state, "cancel")

    def test03_cancel_backorder_cancels_remaining(self):
        """Check that when a move is cancelled and its siblings are all cancelled/done
        and the move contains all of the remaining qty (i.e. it is a backorder from a
        partially completed move), the remaining dependent moves are cancelled.
        """
        # Do half of move1.
        self.move1._set_quantity_done(5)
        self.move1._action_done()
        new_move1 = self.move2.move_orig_ids - self.move1

        # Complete half of move2.
        self.move2._set_quantity_done(5)
        self.move2._action_done()
        new_move2 = new_move1.move_dest_ids - self.move2

        # Cancel the backorder from move1.
        new_move1._action_cancel()

        # Remaining move2 should be cancelled.
        self.assertEqual(new_move2.state, "cancel")


class TestUnreserveIntialDemand(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestUnreserveIntialDemand, cls).setUpClass()
        cls.pack_4apples_info = [{"product": cls.apple, "qty": 4}]
        # Set target storage format to easily pick
        cls.picking_type_pick.u_target_storage_format = "product"

    def test01_do_not_bypass_reservation_update_at_unreserve_initial_demand(self):
        """ When calling _unreserve_initial_demand() disable bypass reservation update
            which is now enabled by default.
        """
        Picking = self.env["stock.picking"]
        apple_quant = self.create_quant(self.apple.id, self.test_location_01.id, 4)
        picking = self.create_picking(
            self.picking_type_pick, products_info=self.pack_4apples_info, confirm=True, assign=True
        )

        self.assertEqual(picking.state, "assigned")
        self.assertEqual(apple_quant.reserved_quantity, 4)
        apple_ml = picking.move_line_ids
        self.assertEqual(len(apple_ml), 1)
        apple_ml.qty_done = 2
        picking.action_done()
        self.assertEqual(picking.state, "done")
        backorder = Picking.get_pickings(backorder_id=picking.id)
        self.assertEqual(backorder.state, "assigned")
