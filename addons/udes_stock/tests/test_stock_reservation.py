"""
Tests for the StockPicking.reserve_stock method.

These tests are separated because they require management of an internal
savepoint because the method manages its own commits and rollbacks.
"""

import itertools
import logging

from . import common

_logger = logging.getLogger(__name__)


_inner_savepoint_seq = itertools.count()


class UDESSavepointTestCase(common.BaseUDES):
    """Responsible for preparing tests with explicit commit/rollback calls.

    odoo.common.SavepointCase creates savepoints which are invalidated if the
    code under test executes explicit commit or rollback calls on the cursor.

    To work around this, this class creates another savepoint for each test
    method, and monkey-patches cursor.commit to do nothing and cursor.rollbck
    to roll back to the inner savepoint.  This preserves the outer savepoint
    and the expected behaviour of odoo.common.SavepointCase.
    """

    def setUp(self):
        """Set up test method environment."""
        super(UDESSavepointTestCase, self).setUp()
        # Set inner savepoint id.
        self._inner_savepoint_id = next(_inner_savepoint_seq)
        self.cr.execute('SAVEPOINT inner_test_%d' % self._inner_savepoint_id)
        # Monkeypatch the cursor.
        self.cr.orig_commit = self.cr.commit
        # Make commit a no-op.
        self.cr.commit = lambda: None
        # Make rollback roll back to the inner savepoint.
        self.cr.orig_rollback = self.cr.rollback
        self.cr.rollback = lambda: self.cr.execute(
            'ROLLBACK TO SAVEPOINT inner_test_%d' % self._inner_savepoint_id)

    def tearDown(self):
        """Tear down test method environment."""
        # Reinstate the cursor's commit and rollback methods.
        self.cr.commit = self.cr.orig_commit
        self.cr.rollback = self.cr.orig_rollback
        super(UDESSavepointTestCase, self).tearDown()


class IndividualPickingReserveStockTestCase(UDESSavepointTestCase):
    """Tests for stock reservation called on individual picking."""

    @classmethod
    def setUpClass(cls):
        super(IndividualPickingReserveStockTestCase, cls).setUpClass()

        # Create stock.
        cls.quant = cls.create_quant(cls.apple.id,
                                     cls.test_location_01.id, 100,
                                     package_id=cls.create_package().id)

        # Set up batch and picking.
        cls.picking_type = cls.picking_type_pick
        batch = cls.create_batch(cls.stock_user)

        products_info = [{'product': cls.apple, 'qty': 10}]
        picking0 = cls.create_picking(cls.picking_type,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      batch_id=batch.id,
                                      confirm=True)
        products_info = [{'product': cls.apple, 'qty': 10}]
        picking1 = cls.create_picking(cls.picking_type,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      batch_id=batch.id,
                                      confirm=True)
        products_info = [{'product': cls.apple, 'qty': 10}]
        picking2 = cls.create_picking(cls.picking_type,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      batch_id=batch.id,
                                      confirm=True)
        cls.picking = picking0
        batch.mark_as_todo()
        cls.batch = batch

    def test00_does_not_reserve_if_reservable_pickings_is_zero(self):
        """Test behaviour when reservable pickings is zero."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 0
        picking_type.u_reserve_batches = True
        picking_type.u_handle_partials = True

        test_picking = self.picking
        original_state = test_picking.state

        # Reserve stock.
        test_picking.reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(0, int(self.quant.reserved_quantity))
        self.assertEqual(original_state, test_picking.state)

    def test01_reserves_stock_to_limit_if_available(self):
        """Test behaviour when stock is a available and reservable pickings is positive."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 1
        picking_type.u_reserve_batches = True
        picking_type.u_handle_partials = True

        test_picking = self.picking
        _logger.info('Picking state: %r', test_picking.state)

        # Get moves for later.
        moves = test_picking.mapped('move_lines')

        # Reserve stock.
        test_picking.reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(30, int(self.quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertEqual('assigned', picking.state)

    def test02_reserves_all_available_stock_if_no_limit_set(self):
        """Test behaviour when stock is a available and reservable pickings is unlimited."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = -1
        picking_type.u_reserve_batches = True
        picking_type.u_handle_partials = True

        test_picking = self.picking

        # Get moves for later.
        pickings = self.batch.mapped('picking_ids')
        moves = pickings.mapped('move_lines')

        # Reserve stock.
        test_picking.reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(30, int(self.quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertTrue(all(x.state == 'assigned' for x in picking))


class PickingReservationTestCase(UDESSavepointTestCase):

    @classmethod
    def setUpClass(cls):
        super(PickingReservationTestCase, cls).setUpClass()

        # Create stock.
        cls.quant = cls.create_quant(cls.apple.id,
                                     cls.test_location_01.id, 100,
                                     package_id=cls.create_package().id)

        # Set up batch and picking.
        cls.picking_type = cls.picking_type_pick
        Picking = cls.env['stock.picking']
        batch = cls.create_batch(cls.stock_user)
        products_info = [{'product': cls.apple, 'qty': 10}]
        picking0 = cls.create_picking(cls.picking_type,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      batch_id=batch.id,
                                      confirm=True)
        Picking |= picking0
        products_info = [{'product': cls.apple, 'qty': 10}]
        picking1 = cls.create_picking(cls.picking_type,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      batch_id=batch.id,
                                      confirm=True)
        Picking |= picking1
        products_info = [{'product': cls.apple, 'qty': 10}]
        picking2 = cls.create_picking(cls.picking_type,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      batch_id=batch.id,
                                      confirm=True)
        Picking |= picking2
        cls.Picking = Picking
        batch.mark_as_todo()
        cls.batch = batch

    def test00_reserves_no_stock_if_limit_is_zero(self):
        """Test behaviour when stock is a available and reservable pickings is unlimited."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 0
        picking_type.u_reserve_batches = False
        picking_type.u_handle_partials = False

        # Get moves for later.
        moves = self.Picking.mapped('move_lines')

        # Reserve stock.
        self.env['stock.picking'].reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(0, int(self.quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertTrue(all(x.state == 'confirmed' for x in picking))

    def test01_reserves_all_available_stock_if_no_limit_set(self):
        """Test behaviour when stock is a available and reservable pickings is unlimited."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = -1
        picking_type.u_reserve_batches = False
        picking_type.u_handle_partials = False

        # Get moves for later.
        moves = self.Picking.mapped('move_lines')

        # Reserve stock.
        self.env['stock.picking'].reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(30, int(self.quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertTrue(all(x.state == 'assigned' for x in picking))

    def test02_reserves_up_to_limit(self):
        """Test behaviour when stock is a available and reservable pickings is limited."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 1
        picking_type.u_reserve_batches = False
        picking_type.u_handle_partials = False

        # Get moves for later.
        moves = self.Picking.mapped('move_lines')

        # Reserve stock.
        self.env['stock.picking'].reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(10, int(self.quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertEqual(1, picking.mapped('state').count('assigned'))

    def test03_reserves_batch(self):
        """Test complete batch is reserved if the reserve batch flag is set."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 1
        picking_type.u_reserve_batches = True
        picking_type.u_handle_partials = False

        # Get moves for later.
        moves = self.Picking.mapped('move_lines')

        # Reserve stock.
        self.env['stock.picking'].reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(30, int(self.quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertTrue(all(x.state == 'assigned' for x in picking))

    def test04_reserves_available_stock_for_batch(self):
        """Reserve as much stock as possible for a batch."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 1
        picking_type.u_reserve_batches = True
        picking_type.u_handle_partials = False

        # Create an unsatisfiable picking.
        products_info = [{'product': self.apple, 'qty': 200}]
        picking = self.create_picking(picking_type,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      batch_id=self.batch.id,
                                      confirm=True)
        self.Picking |= picking

        # Get moves for later.
        moves = self.Picking.mapped('move_lines')

        # Reserve stock.
        self.env['stock.picking'].reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(100, int(self.quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        assigned = picking.filtered(lambda x: x.state == 'assigned')
        confirmed = picking.filtered(lambda x: x.state == 'confirmed')
        self.assertEqual(3, len(assigned))
        self.assertEqual(1, len(confirmed))

    def test05_does_not_reserve_if_insufficient_stock(self):
        """Does not reserve if insufficient stock and reserve batch and handle partial are off."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 4
        picking_type.u_reserve_batches = False
        picking_type.u_handle_partials = False

        # Create an unsatisfiable picking.
        products_info = [{'product': self.apple, 'qty': 200}]
        picking = self.create_picking(picking_type,
                                      origin="test_picking_origin",
                                      products_info=products_info,
                                      batch_id=self.batch.id,
                                      confirm=True)
        self.Picking |= picking

        # Get moves for later.
        moves = self.Picking.mapped('move_lines')

        # Reserve stock.
        self.env['stock.picking'].reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(100, int(self.quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        assigned = picking.filtered(lambda x: x.state == 'assigned')
        confirmed = picking.filtered(lambda x: x.state == 'confirmed')
        self.assertEqual(3, len(assigned))
        self.assertEqual(1, len(confirmed))
