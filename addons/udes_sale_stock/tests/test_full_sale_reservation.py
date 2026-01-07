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
