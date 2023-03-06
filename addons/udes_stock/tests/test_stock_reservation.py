"""
Tests for StockPicking.reserve_stock.

The method itself cannot be tested because it contains a commit statement, but
we can test related methods.
"""
import logging
from unittest import mock
from .common import BaseUDES


class FindUnreservableMovesTestCase(BaseUDES):
    """Test cases for StockPicking._find_unreservable_moves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_quant(cls.apple.id, cls.test_location_01.id, 10)

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
        logger = "odoo.addons.udes_stock.models.stock_picking"

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
        logger = "odoo.addons.udes_stock.models.stock_picking"

        with self.assertLogs(logger, logging.DEBUG) as cm:
            picking._find_unreservable_moves()
        messages = [r.getMessage() for r in cm.records]
        self.assertEqual(
            messages, ["Checking reservability for 1 pickings.", "Checking pickings 0-0"]
        )


# Reserve Stock tests.

# The principal conditions that affect stock reservation are whether a picking
# is in a batch, and the values of the picking type's u_reserve_batches and
# u_handle_partial flags. The stock level conditions that affect reservation
# are: sufficent stock, no stock, some lines are not reservable and some lines
# are partially available.

# To test this, we have a matrix of configuration options, initial stock levels
# and expected reservations. The ReservationMixin class has tests for each of
# the stock level conditions; the TestCase classes provide the configuration
# for each test method.

# Test configuration, stock levels and expected outputs, keyed on:
# Pickings are in batches, PickingType.u_reserve_batches, PickingType.u_handle_partials.
# Values order: all available, none available, partially available, line partially available
# In-values order:
# quantity in stock, expected reservation
# each picking has two identical lines (2 x 10)
# each batch has two identical pickings
RESERVATION_MATRIX = {
    (True, True, True): [(40, 40), (0, 0), (30, 30), (35, 35)],
    (True, True, False): [(40, 40), (0, 0), (0, 0), (0, 0)],
    (True, False, True): [(40, 40), (0, 0), (30, 30), (35, 35)],
    (True, False, False): [(40, 40), (0, 0), (30, 20), (35, 20)],
    (False, True, True): [(40, 40), (0, 0), (40, 40), (40, 40)],
    (False, True, False): [(40, 40), (0, 0), (0, 0), (0, 0)],
    (False, False, True): [(40, 40), (0, 0), (30, 30), (35, 35)],
    (False, False, False): [(40, 40), (0, 0), (0, 0), (0, 0)],
}


class ReservationMixin(object):
    def test_reserves_stock_when_sufficient_stock_is_available(self):
        """The system will reserve all demand if stock is available."""
        initial_qty, expected = self.config[0]
        self.setup(initial_qty)

        with mock.patch.object(self.pick.env.cr, "commit", return_value=None):
            self.pick.reserve_stock()

        quant = self.Quant.search([("reserved_quantity", ">", 0)])
        self.assertEqual(quant.reserved_quantity, expected)

    def test_does_not_reserve_if_no_available_stock(self):
        """The system will not reserve stock if none is available."""
        initial_qty, expected = self.config[1]
        self.setup(initial_qty)

        with mock.patch.object(self.pick.env.cr, "commit", return_value=None):
            self.pick.reserve_stock()

        quant = self.Quant.search([("reserved_quantity", ">", 0)])
        self.assertEqual(quant.reserved_quantity, expected)

    def test_handles_partially_available_pickings(self):
        """The system will correctly handle the case when not all lines can be reserved."""
        initial_qty, expected = self.config[2]
        self.setup(initial_qty)

        with mock.patch.object(self.pick.env.cr, "commit", return_value=None):
            self.pick.reserve_stock()

        quant = self.Quant.search([("reserved_quantity", ">", 0)])
        self.assertEqual(quant.reserved_quantity, expected)

    def test_handles_partially_available_lines(self):
        """The system will correctly handle the case when a line is partially available."""
        initial_qty, expected = self.config[2]
        self.setup(initial_qty)

        with mock.patch.object(self.pick.env.cr, "commit", return_value=None):
            self.pick.reserve_stock()

        quant = self.Quant.search([("reserved_quantity", ">", 0)])
        self.assertEqual(quant.reserved_quantity, expected)


class ReservationBase(BaseUDES):
    """Test cases for stock reservation."""

    KEY = ()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Pick = cls.env["stock.picking"]
        cls.Quant = cls.env["stock.quant"]

        cls.picking_type_pick.u_num_reservable_pickings = 100
        batched, reserve_batches, handle_partials = cls.KEY
        cls.batched = batched
        cls.config = RESERVATION_MATRIX[cls.KEY]
        cls.picking_type_pick.u_reserve_batches = reserve_batches
        cls.picking_type_pick.u_handle_partials = handle_partials

        cls.Pick = Pick
        cls.pick = Pick.browse()

    def setup(self, initial_quantity):
        """Create two pickings with two lines of 10, batch if required."""
        self.create_quant(self.apple.id, self.test_location_01.id, initial_quantity)
        products_info = [{"product": self.apple, "qty": 10}] * 2
        pickings = self.create_picking(self.picking_type_pick, products_info, confirm=True)
        pickings |= self.create_picking(self.picking_type_pick, products_info, confirm=True)
        if self.batched:
            batch = self.create_batch()
            pickings.write({"batch_id": batch.id})
            batch.mark_as_todo()
        return pickings


class BatchedReserveBatchHandlePartialsTestCase(ReservationBase, ReservationMixin):
    """Test cases for stock reservation."""

    KEY = True, True, True


class BatchedReserveBatchNoHandlePartialsTestCase(ReservationBase, ReservationMixin):
    """Test cases for stock reservation."""

    KEY = True, True, False


class BatchedNoReserveBatchHandlePartialsTestCase(ReservationBase, ReservationMixin):
    """Test cases for stock reservation."""

    KEY = True, False, True


class BatchedNoReserveBatchNoHandlePartialsTestCase(ReservationBase, ReservationMixin):
    """Test cases for stock reservation."""

    KEY = True, False, False


class UnbatchedReserveBatchHandlePartialsTestCase(ReservationBase, ReservationMixin):
    """Test cases for stock reservation."""

    KEY = False, True, True


class UnbatchedReserveBatchNoHandlePartialsTestCase(ReservationBase, ReservationMixin):
    """Test cases for stock reservation."""

    KEY = False, True, False


class UnbatchedNoReserveBatchHandlePartialsTestCase(ReservationBase, ReservationMixin):
    """Test cases for stock reservation."""

    KEY = False, False, True


class UnbatchedNoReserveBatchNoHandlePartialsTestCase(ReservationBase, ReservationMixin):
    """Test cases for stock reservation."""

    KEY = False, False, False
