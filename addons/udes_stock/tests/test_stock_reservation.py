"""
Tests for StockPicking.reserve_stock.

The method itself cannot be tested because it contains a commit statement, but
we can test related methods.
"""
import contextlib
import logging
from unittest import mock
import uuid

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
    """Tests for the criteria in the reservation matrix."""

    def test_reserves_stock_in_accordance_with_picking_type_flags(self):
        """The system will respect picking type configuration when reserving stock."""
        messages = [
            "Case: there is enough stock for all lines",
            "Case: there is no stock for any lines",
            "Case: there is no stock for one line",
            "Case: there is partial stock for one line",
        ]
        for message, (initial_qty, expected) in zip(messages, self.config):
            with self.subTest(
                msg=message,
                batched=self.batched,
                reserve_batches=self.picking_type_pick.u_reserve_batches,
                handle_partials=self.picking_type_pick.u_handle_partials,
            ):
                with self.savepoint():
                    # Run inside a savepoint so that changes to pickings and quants
                    # etc. are reversed after each subtest.
                    self.create_quant(self.apple.id, self.test_location_01.id, initial_qty)

                    with mock.patch.object(self.pick.env.cr, "commit", return_value=None):
                        self.pick.reserve_stock()

                    quant = self.Quant.search([("reserved_quantity", ">", 0)])
                    self.assertEqual(quant.reserved_quantity, expected)


class SavepointMixin:
    """
    Provides a context manager that creates a savepoint and rolls back on exit.

    This can be used to reverse state changes made during subtests, as there is
    no automatic rollback after a subtest iteration completes.

    (The core Cursor.savepoint() releases the savepoint on exit, and
    doesn't expose its name so we can't roll it back ourselves.
    """

    @contextlib.contextmanager
    def savepoint(self):
        """A savepoint that always rolls back."""
        # This is how Odoo core name their savepoints.
        name = uuid.uuid1().hex
        self.cr.execute(f'SAVEPOINT "{name}"')
        try:
            yield
        finally:
            self.cr.execute(f'ROLLBACK TO SAVEPOINT "{name}"')


class ReservationBase(BaseUDES, SavepointMixin):
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

        # Create two pickings with two lines of 10, batch if required.
        products_info = [{"product": cls.apple, "qty": 10}] * 2
        pickings = cls.create_picking(cls.picking_type_pick, products_info, confirm=True)
        pickings |= cls.create_picking(cls.picking_type_pick, products_info, confirm=True)
        if cls.batched:
            batch = cls.create_batch()
            pickings.write({"batch_id": batch.id})
            batch.mark_as_todo()

    def setup(self, initial_quantity):
        self.create_quant(self.apple.id, self.test_location_01.id, initial_quantity)
        return


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


class NumReservablePickingsTestCase(BaseUDES, SavepointMixin):
    """Tests for the StockPickingType.u_num_reservable_pickings settings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Pick = cls.env["stock.picking"]
        cls.Quant = cls.env["stock.quant"]

        cls.picking_type_pick.u_handle_partials = True

        cls.pick = Pick.browse()
        cls.Pick = Pick

    def test_respects_number_of_reservable_pickings(self):
        """The system will respect the value of
        StockPickingType.u_num_reservable_pickings"""
        expected = (0, 10, 20)
        values = (0, 1, -1)
        messages = [
            "Case: reserve no stock",
            "Case: reserve stock for a limited number of pickings",
            "Case: reserve as much stock as possible",
        ]
        quant = self.create_quant(self.apple.id, self.test_location_01.id, qty=30)
        products_info = [{"product": self.apple, "qty": 10}]
        pickings = self.create_picking(
            self.picking_type_pick, products_info=products_info, confirm=True
        )
        pickings |= self.create_picking(
            self.picking_type_pick, products_info=products_info, confirm=True
        )

        for message, value, expected in zip(messages, values, expected):
            with self.subTest(msg=message, u_num_reservable_pickings=value):
                # Run inside a savepoint so that changes to pickings and quants
                # etc. are reversed after each subtest.
                with self.savepoint():
                    self.picking_type_pick.u_num_reservable_pickings = value

                    with mock.patch.object(self.pick.env.cr, "commit", return_value=None):
                        self.pick.reserve_stock()

                    self.assertEqual(quant.reserved_quantity, expected)


class ReservationGeneralTestCase(BaseUDES):
    """Stock reservation tests not covered by other testcases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Pick = cls.env["stock.picking"]

        cls.pick = Pick.browse()

    def test_does_not_exceed_reservation_limit(self):
        """Do not reserve more pickings than specified by u_num_reservable_pickings."""
        self.picking_type_pick.u_num_reservable_pickings = 2
        self.picking_type_pick.u_reserve_batches = True
        expected = 20
        quant = self.create_quant(self.apple.id, self.test_location_01.id, qty=30)
        products_info = [{"product": self.apple, "qty": 10}]
        picking = self.create_picking(
            self.picking_type_pick, products_info=products_info, confirm=True
        )
        batch1 = self.create_batch()
        picking.batch_id = batch1
        picking = self.create_picking(
            self.picking_type_pick, products_info=products_info, confirm=True
        )
        batch2 = self.create_batch()
        picking.batch_id = batch2
        picking = self.create_picking(
            self.picking_type_pick, products_info=products_info, confirm=True
        )
        picking.batch_id = batch1
        batch1.mark_as_todo()
        batch2.mark_as_todo()

        with mock.patch.object(self.pick.env.cr, "commit", return_value=None):
            self.pick.reserve_stock()

        self.assertEqual(quant.reserved_quantity, expected)

    def test_does_not_let_unfulfillable_picking_block_later_reservation(self):
        """A picking that cannot be fully reserved must affect later pickings."""
        self.picking_type_pick.u_num_reservable_pickings = 3
        self.picking_type_pick.u_handle_partials = False
        self.create_quant(self.banana.id, self.test_location_01.id, qty=20)
        demand1 = [{"product": self.banana, "qty": 10}]
        demand2 = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
        picking1 = self.create_picking(self.picking_type_pick, products_info=demand1, confirm=True)
        picking2 = self.create_picking(self.picking_type_pick, products_info=demand2, confirm=True)
        picking3 = self.create_picking(self.picking_type_pick, products_info=demand1, confirm=True)

        with mock.patch.object(self.pick.env.cr, "commit", return_value=None):
            self.pick.reserve_stock()

        self.assertEqual(picking1.state, "assigned")
        self.assertEqual(picking2.state, "confirmed")
        self.assertEqual(picking3.state, "assigned")
