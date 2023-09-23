"""Unit tests for stock reservation."""
from unittest import mock

import logging
from odoo.addons.udes_stock.tests.common import BaseUDES
from odoo.exceptions import UserError
from odoo.tests import get_db_name
import odoo


class TestStockPicking(BaseUDES):
    @classmethod
    def setUpClass(cls):
        """
        Need to include methods enter_test_mode() and leave_test_mode()
        This will allow for the database to be rolled back after the tests are finished
        Without these methods the database can't be rolledback due to a cr.commit() in the method in test (reserve_stock)
        """
        cls.registry = odoo.registry(get_db_name())
        cls.cr = cls.registry.cursor()
        cls.registry.enter_test_mode(cls.cr)
        super(TestStockPicking, cls).setUpClass()

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
        pick_location = Location.create(
            {
                "name": "Pick Location 01",
                "barcode": "LPICKLOCATION01",
                "usage": "internal",
                "location_id": picking_zone.id,
            }
        )
        cls.picking_type_pick.default_location_src_id = picking_zone

        products_info = [{"product": cls.apple, "uom_qty": 10.0}]

        cls.picking_type_pick.u_num_reservable_pickings = -1

        # Create a picking with a move
        cls.test_picking_pick = cls.create_picking(
            cls.picking_type_pick,
            products_info=products_info,
            confirm=True,
            assign=False,
            location_dest_id=cls.test_received_location_01.id,
        )

        # Create an available quantity of apples
        cls.test_quant_apple = cls.create_quant(
            product_id=cls.apple.id,
            location_id=pick_location.id,
            qty=10.0,
        )

        # Mock the find unreservable moves method to simulate allocation
        # failure.
        cls.mock_find_unreservable_moves = mock.patch.object(
            cls.Picking.__class__,
            "_find_unreservable_moves",
            return_value=cls.Move.browse(),
        )

    @classmethod
    def tearDownClass(cls):
        super(TestStockPicking, cls).tearDownClass()
        cls.registry.leave_test_mode()

    def test_reserve_available_stock(self):
        """
        Check there is stock available
        Check there is no reserved quantity and that the stock_picking is in state 'confirmed'
        Run reserve_stock, which should then reserve quantity and change state of stock_picking
        """
        self.assertEqual(self.test_quant_apple.quantity, 10.0)

        move = self.test_picking_pick.move_lines
        move = self.test_picking_pick.move_lines
        self.assertEqual(len(move), 1)

        self.assertEqual(move.reserved_availability, 0.0)
        self.assertEqual(move.state, "confirmed")

        self.test_picking_pick.reserve_stock()

        self.assertEqual(move.reserved_availability, 10.0)
        self.assertEqual(move.state, "assigned")
        self.assertEqual(self.test_picking_pick.state, "assigned")

    def test_reserve_unavailable_stock(self):
        """
        Check that a stock picking with no stock available cannot reserve stock
        """
        products_info = [{"product": self.banana, "uom_qty": 10.0}]
        self.test_picking_pick = self.create_picking(
            self.picking_type_pick,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,
        )

        move = self.test_picking_pick.move_lines
        self.assertEqual(len(move), 1)
        self.assertEqual(move.name, "Test product Banana")
        self.assertEqual(move.reserved_availability, 0.0)
        self.assertEqual(move.state, "confirmed")

        with self.mock_find_unreservable_moves:
            with self.assertRaises(UserError) as e:
                self.test_picking_pick.reserve_stock()

        products = move.mapped("product_id").name_get()
        products = products[0][1]
        picks = move.mapped("picking_id.name")
        msg = f"Unable to reserve stock for products {products} for pickings {picks}."
        self.assertEqual(e.exception.args[0], msg)

        self.assertEqual(move.reserved_availability, 0.0)
        self.assertEqual(move.state, "confirmed")
        self.assertEqual(self.test_picking_pick.state, "confirmed")


class FindUnreservableMovesTestCase(BaseUDES):
    """Test cases for StockPicking._find_unreservable_moves."""

    @classmethod
    def setUpClass(cls):  # noqa: D102
        super().setUpClass()
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)

    def test_does_not_report_moves_if_stock_is_available(self):
        """The system will not report moves if there is enough stock to reserve."""
        self.picking_type_pick.u_handle_partials = False
        products_info = [{"product": self.apple, "qty": 10}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)

        unreservable_moves = picking._find_unreservable_moves()

        self.assertFalse(unreservable_moves)

    def test_reports_moves_if_stock_is_not_available(self):
        """The system will report moves for which there is insufficient stock."""
        self.picking_type_pick.u_handle_partials = False
        products_info = [{"product": self.banana, "qty": 10}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)

        unreservable_moves = picking._find_unreservable_moves()

        self.assertEqual(unreservable_moves, picking.move_lines)

    def test_ignores_cancelled_moves(self):
        """The system will disregard moves which are cancelled when reporting."""
        # The same logic applies to assigned and done states.
        self.picking_type_pick.u_handle_partials = False
        products_info = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)
        move = picking.move_lines.filtered(lambda m: m.product_id == self.banana)
        move._action_cancel()

        unreservable_moves = picking._find_unreservable_moves()

        self.assertFalse(unreservable_moves)

    def test_allows_partially_fulfilled_lines_if_handle_partials_is_on(self):
        """The system will not report partially reserved moves if u_handle_partials is True."""
        self.picking_type_pick.u_handle_partials = True
        products_info = [{"product": self.apple, "qty": 15}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)

        unreservable_moves = picking._find_unreservable_moves()

        self.assertFalse(unreservable_moves)

    def test_prohibits_partially_fulfilled_lines_if_handle_partials_is_off(self):
        """The system will report partially reservable moves if u_handle_partials is False."""
        self.picking_type_pick.u_handle_partials = False
        products_info = [{"product": self.apple, "qty": 15}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)

        unreservable_moves = picking._find_unreservable_moves()

        self.assertEqual(unreservable_moves, picking.move_lines)

    def test_logs_info_message_if_more_than_one_picking_processed(self):
        """The system will log an INFO level message if more than one picking is processed."""
        products_info = [{"product": self.apple, "qty": 5}]
        pickings = self.create_picking(self.picking_type_pick, products_info, confirm=True)
        pickings |= self.create_picking(self.picking_type_pick, products_info, confirm=True)
        logger = "odoo.addons.udes_stock_cron.models.stock_picking"

        with self.assertLogs(logger, logging.INFO) as cm:
            pickings._find_unreservable_moves()
        messages = [r.getMessage() for r in cm.records]
        self.assertEqual(
            messages, ["Checking reservability for 2 pickings.", "Checking pickings 0-1"]
        )

    def test_logs_debug_message_if_more_one_picking_processed(self):
        """The system will log a DEBUG level message if only one picking is processed."""
        products_info = [{"product": self.apple, "qty": 5}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)
        logger = "odoo.addons.udes_stock_cron.models.stock_picking"

        with self.assertLogs(logger, logging.DEBUG) as cm:
            picking._find_unreservable_moves()
        messages = [r.getMessage() for r in cm.records]
        self.assertEqual(
            messages, ["Checking reservability for 1 pickings.", "Checking pickings 0-0"]
        )
