"""Unit tests for full sale reservation"""

from unittest import mock
from odoo.addons.udes_common.tests.common import SavepointMixin
from .common import BaseSaleUDES
import datetime
from odoo.exceptions import UserError


class TestFullSaleReservation(BaseSaleUDES):
    @classmethod
    def setUpClass(cls):
        super(TestFullSaleReservation, cls).setUpClass()

        Location = cls.env["stock.location"]
        cls.Move = cls.env["stock.move"]
        cls.Picking = cls.env["stock.picking"]

        picking_zone = Location.create(
            {
                "name": "Picking Zone",
                "barcode": "LPICKINGZONE",
                "usage": "view",
                "location_id": cls.warehouse.id,
            }
        )
        cls.pick_location = Location.create(
            {
                "name": "Pick Location 01",
                "barcode": "LPICKLOCATION01",
                "usage": "internal",
                "location_id": picking_zone.id,
            }
        )
        picking_zone2 = Location.create(
            {
                "name": "Picking Zone 2",
                "barcode": "LPICKINGZONE2",
                "usage": "view",
                "location_id": cls.warehouse.id,
            }
        )
        cls.pick_location_2 = Location.create(
            {
                "name": "Pick Location 02",
                "barcode": "LPICKLOCATION02",
                "usage": "internal",
                "location_id": picking_zone2.id,
            }
        )
        cls.picking_type_pick.default_location_src_id = picking_zone
        cls.picking_type_pick.u_num_reservable_pickings = -1
        # Not allowing handle partials.
        cls.picking_type_pick.u_handle_partials = False
        # Copy picking type to have same configurations, and only changing the source location.
        cls.picking_type_pick2 = cls.picking_type_pick.copy(
            {"default_location_src_id": picking_zone2.id}
        )

        products_info = [{"product": cls.apple, "uom_qty": 10.0}]

        # Create first picking with a move
        cls.test_picking_pick1 = cls.create_picking(
            cls.picking_type_pick,
            products_info=products_info,
            confirm=True,
            assign=False,
            location_dest_id=cls.test_received_location_01.id,
        )
        # Creating second picking with a different move
        products_info = [{"product": cls.banana, "uom_qty": 5.0}]
        cls.test_picking_pick2 = cls.create_picking(
            cls.picking_type_pick2,
            products_info=products_info,
            confirm=True,
            assign=False,
            location_dest_id=cls.test_received_location_01.id,
        )

        # Create a sale order with same qty of apples and bananas
        customer = cls.create_partner(
            "Test Customer",
        )
        cls.sale = cls.create_sale(
            customer, client_order_ref="order01", requested_date=datetime.date.today()
        )
        cls.sale_line1 = cls.create_sale_line(cls.sale, cls.apple, 10.0)
        cls.sale_line2 = cls.create_sale_line(cls.sale, cls.banana, 5.0)
        # Update move lines to link each move line with respective sale order line
        cls.test_picking_pick1.move_lines.write({"sale_line_id": cls.sale_line1.id})
        cls.test_picking_pick2.move_lines.write({"sale_line_id": cls.sale_line2.id})

        # Mock the find unreservable moves method to simulate allocation
        # failure.
        cls.mock_find_unreservable_moves = mock.patch.object(
            cls.Picking.__class__,
            "_find_unreservable_moves",
            return_value=cls.Move.browse(),
        )

    def test_dont_reserve_not_fully_available_stock(self):
        """
        Check there is stock available
        Check there is no reserved quantity and that the stock_picking is in state 'confirmed'
        Run reserve_stock, which should then reserve quantity and change state of stock_picking
        """
        # Create an available quantity of apples
        test_quant_apple = self.create_quant(
            product_id=self.apple.id,
            location_id=self.pick_location.id,
            qty=10.0,
        )
        self.picking_type_pick.u_full_sale_reservation = True
        self.picking_type_pick2.u_full_sale_reservation = True
        self.assertEqual(test_quant_apple.quantity, 10.0)

        move1 = self.test_picking_pick1.move_lines
        self.assertEqual(len(move1), 1)

        move2 = self.test_picking_pick2.move_lines
        self.assertEqual(len(move2), 1)

        self.assertEqual(move1.reserved_availability, 0.0)
        self.assertEqual(move1.state, "confirmed")

        self.assertEqual(move2.reserved_availability, 0.0)
        self.assertEqual(move2.state, "confirmed")

        with self.mock_find_unreservable_moves:
            with self.assertRaises(UserError) as e:
                self.test_picking_pick1.reserve_stock()

        products = move2.mapped("product_id").name_get()
        products = products[0][1]
        picks = move2.mapped("picking_id.name")
        msg = f"Unable to reserve stock for products {products} for pickings {picks}."
        self.assertEqual(e.exception.args[0], msg)

        self.assertEqual(move1.reserved_availability, 0.0)
        self.assertEqual(move1.state, "confirmed")
        self.assertEqual(self.test_picking_pick1.state, "confirmed")

        self.assertEqual(move2.reserved_availability, 0.0)
        self.assertEqual(move2.state, "confirmed")
        self.assertEqual(self.test_picking_pick2.state, "confirmed")

        # If Full Sale Reservation is turned off able to reserve picking which have available stock.
        self.picking_type_pick.u_full_sale_reservation = False
        self.picking_type_pick2.u_full_sale_reservation = False

        self.test_picking_pick1.reserve_stock()

        self.assertEqual(move1.reserved_availability, 10.0)
        self.assertEqual(move1.state, "assigned")
        self.assertEqual(self.test_picking_pick1.state, "assigned")

        self.assertEqual(move2.reserved_availability, 0.0)
        self.assertEqual(move2.state, "confirmed")
        self.assertEqual(self.test_picking_pick2.state, "confirmed")

    def test_reserve_when_fully_available_stock(self):
        # Create an available quantity of apples
        test_quant_apple = self.create_quant(
            product_id=self.apple.id,
            location_id=self.pick_location.id,
            qty=10.0,
        )
        self.assertEqual(test_quant_apple.quantity, 10.0)

        test_quant_banana = self.create_quant(
            product_id=self.banana.id,
            location_id=self.pick_location_2.id,
            qty=5,
        )
        self.assertEqual(test_quant_banana.quantity, 5.0)

        self.picking_type_pick.u_full_sale_reservation = True
        self.picking_type_pick2.u_full_sale_reservation = True
        self.assertEqual(test_quant_apple.quantity, 10.0)

        move1 = self.test_picking_pick1.move_lines
        self.assertEqual(len(move1), 1)

        move2 = self.test_picking_pick2.move_lines
        self.assertEqual(len(move2), 1)

        # It will automatically pull second pick because they are linked with same sale order
        self.test_picking_pick1.reserve_stock()

        self.assertEqual(move1.reserved_availability, 10.0)
        self.assertEqual(move1.state, "assigned")
        self.assertEqual(self.test_picking_pick1.state, "assigned")

        self.assertEqual(move2.reserved_availability, 5.0)
        self.assertEqual(move2.state, "assigned")
        self.assertEqual(self.test_picking_pick2.state, "assigned")

    def test_block_unreserves_all_pickings_of_full_sale_reservation(self):
        """
        Blocking stock reserved by a picking with full sale reservation unreserves all the
        pickings of its sale order after a confirmation, as they are reserved together
        """
        BlockReservationWizard = self.env["block.reservation.wizard"]
        self.create_quant(product_id=self.apple.id, location_id=self.pick_location.id, qty=10.0)
        self.create_quant(product_id=self.banana.id, location_id=self.pick_location_2.id, qty=5)
        pickings = self.test_picking_pick1 | self.test_picking_pick2
        # Handle partials, so only the full sale reservation unreserves the other picking
        pickings.picking_type_id.write({"u_full_sale_reservation": True, "u_handle_partials": True})
        self.test_picking_pick1.reserve_stock()
        self.assertEqual(set(pickings.mapped("state")), {"assigned"})

        action = self.pick_location.button_block_wizard()
        wizard = BlockReservationWizard.browse(action["res_id"])
        self.assertFalse(wizard.unreservable_move_line_ids)
        self.assertEqual(
            wizard.full_reservation_move_line_ids, self.test_picking_pick1.move_line_ids
        )
        self.assertEqual(wizard.full_reservation_picking_ids, pickings)

        wizard.u_blocked_reason = "Shelves fell over"
        wizard.action_confirm()
        self.assertTrue(self.pick_location.u_blocked)
        self.assertFalse(pickings.move_line_ids)
        self.assertEqual(set(pickings.mapped("state")), {"confirmed"})

    def test_block_unreserves_sale_pickings_of_picking_in_batch_reserved_atomically(self):
        """
        Blocking stock reserved by a picking with full sale reservation, which is also in a
        batch reserved atomically, unreserves all the pickings of its sale order
        """
        BlockReservationWizard = self.env["block.reservation.wizard"]
        Batch = self.env["stock.picking.batch"]
        self.create_quant(product_id=self.apple.id, location_id=self.pick_location.id, qty=10.0)
        self.create_quant(product_id=self.banana.id, location_id=self.pick_location_2.id, qty=5)
        pickings = self.test_picking_pick1 | self.test_picking_pick2
        pickings.picking_type_id.write(
            {"u_full_sale_reservation": True, "u_handle_partials": True, "u_reserve_batches": True}
        )
        batch = Batch.create({"picking_ids": [(6, 0, self.test_picking_pick1.ids)]})
        batch.mark_as_todo()
        self.test_picking_pick1.reserve_stock()
        self.assertEqual(set(pickings.mapped("state")), {"assigned"})

        action = self.pick_location.button_block_wizard()
        wizard = BlockReservationWizard.browse(action["res_id"])
        self.assertEqual(
            wizard.full_reservation_move_line_ids, self.test_picking_pick1.move_line_ids
        )
        self.assertEqual(wizard.full_reservation_picking_ids, pickings)

        wizard.u_blocked_reason = "Shelves fell over"
        wizard.action_confirm()
        self.assertTrue(self.pick_location.u_blocked)
        self.assertFalse(pickings.move_line_ids)
        self.assertEqual(set(pickings.mapped("state")), {"confirmed"})

    def test_block_unreserves_sale_pickings_of_other_pickings_in_batch_reserved_atomically(self):
        """
        Blocking stock reserved by a picking in a batch reserved atomically unreserves the
        pickings of the sale orders of the other pickings in the batch too, as reserving the
        batch reserves all of them together
        """
        BlockReservationWizard = self.env["block.reservation.wizard"]
        Batch = self.env["stock.picking.batch"]
        self.create_quant(product_id=self.apple.id, location_id=self.pick_location.id, qty=10.0)
        self.create_quant(product_id=self.cherry.id, location_id=self.pick_location.id, qty=5.0)
        self.create_quant(product_id=self.banana.id, location_id=self.pick_location_2.id, qty=10)
        # A second sale order with a picking in the batch and a picking outside it
        test_picking_pick3 = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.cherry, "uom_qty": 5.0}],
            confirm=True,
            assign=False,
            location_dest_id=self.test_received_location_01.id,
        )
        test_picking_pick4 = self.create_picking(
            self.picking_type_pick2,
            products_info=[{"product": self.banana, "uom_qty": 5.0}],
            confirm=True,
            assign=False,
            location_dest_id=self.test_received_location_01.id,
        )
        sale2 = self.create_sale(
            self.sale.partner_id, client_order_ref="order02", requested_date=datetime.date.today()
        )
        test_picking_pick3.move_lines.write(
            {"sale_line_id": self.create_sale_line(sale2, self.cherry, 5.0).id}
        )
        test_picking_pick4.move_lines.write(
            {"sale_line_id": self.create_sale_line(sale2, self.banana, 5.0).id}
        )
        pickings = (
            self.test_picking_pick1
            | self.test_picking_pick2
            | test_picking_pick3
            | test_picking_pick4
        )
        pickings.picking_type_id.write(
            {"u_full_sale_reservation": True, "u_handle_partials": True, "u_reserve_batches": True}
        )
        batch = Batch.create(
            {"picking_ids": [(6, 0, (self.test_picking_pick1 | test_picking_pick3).ids)]}
        )
        batch.mark_as_todo()
        self.test_picking_pick1.reserve_stock()
        self.assertEqual(set(pickings.mapped("state")), {"assigned"})

        # Block the cherries, reserved by the picking of the second sale order in the batch
        action = self.cherry.button_block_wizard()
        wizard = BlockReservationWizard.browse(action["res_id"])
        self.assertEqual(wizard.full_reservation_move_line_ids, test_picking_pick3.move_line_ids)
        self.assertEqual(wizard.full_reservation_picking_ids, pickings)

        wizard.u_blocked_reason = "Damaged cherries"
        wizard.action_confirm()
        self.assertTrue(self.cherry.u_blocked)
        self.assertFalse(pickings.move_line_ids)
        self.assertEqual(set(pickings.mapped("state")), {"confirmed"})
