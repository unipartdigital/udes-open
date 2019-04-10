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

    def test00_does_not_reserve_if_reservable_pickings_is_zero(self):
        """Test behaviour when reservable pickings is zero."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 0
        picking_type.u_reserve_batch = True
        picking_type.u_handle_partials = True

        # Create stock.
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 100,
                                  package_id=self.create_package().id)

        # Set up batch and picking.
        batch = self.create_batch(self.stock_user)
        products_info = [{'product': self.apple, 'qty': 10}]
        test_picking = self.create_picking(picking_type,
                                           origin="test_picking_origin",
                                           products_info=products_info,
                                           batch_id=batch.id,
                                           confirm=True)
        batch.mark_as_todo()
        original_state = test_picking.state

        # Reserve stock.
        test_picking.reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(0, int(quant.reserved_quantity))
        self.assertEqual(original_state, test_picking.state)

    def test01_reserves_stock_to_limit_if_available(self):
        """Test behaviour when stock is a available and reservable pickings is positive."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 1
        picking_type.u_reserve_batch = True
        picking_type.u_handle_partials = True

        # Create stock.
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 100,
                                  package_id=self.create_package().id)

        # Set up batch and picking.
        batch = self.create_batch(self.stock_user)
        products_info = [{'product': self.apple, 'qty': 10}]
        test_picking = self.create_picking(picking_type,
                                           origin="test_picking_origin",
                                           products_info=products_info,
                                           batch_id=batch.id,
                                           confirm=True)
        _logger.info('Picking state: %r', test_picking.state)
        batch.mark_as_todo()

        # Get moves for later.
        moves = test_picking.mapped('move_lines')

        # Reserve stock.
        test_picking.reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(10, int(quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertEqual('assigned', picking.state)

    def test02_reserves_all_available_stock_if_no_limit_set(self):
        """Test behaviour when stock is a available and reservable pickings is unlimited."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = -1
        picking_type.u_reserve_batch = True
        picking_type.u_handle_partials = True

        # Create stock.
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 100,
                                  package_id=self.create_package().id)

        # Set up batch and picking.
        Picking = self.env['stock.picking']
        batch = self.create_batch(self.stock_user)
        products_info = [{'product': self.apple, 'qty': 20}]
        test_picking = self.create_picking(picking_type,
                                           origin="test_picking_origin",
                                           products_info=products_info,
                                           batch_id=batch.id,
                                           confirm=True)
        Picking |= test_picking
        products_info = [{'product': self.apple, 'qty': 10}]
        other_picking = self.create_picking(picking_type,
                                            origin="test_picking_origin",
                                            products_info=products_info,
                                            batch_id=batch.id,
                                            confirm=True)
        Picking |= other_picking
        assert len(Picking) == 2
        assert len(batch.picking_ids) == 2
        batch.mark_as_todo()

        # Get moves for later.
        moves = Picking.mapped('move_lines')

        # Reserve stock.
        test_picking.reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(30, int(quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertTrue(all(x.state == 'assigned' for x in picking))


class PickingReservationTestCase(UDESSavepointTestCase):

    def test00_reserves_all_available_stock_if_no_limit_set(self):
        """Test behaviour when stock is a available and reservable pickings is unlimited."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = -1
        picking_type.u_reserve_batch = True
        picking_type.u_handle_partials = True

        # Create stock.
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 100,
                                  package_id=self.create_package().id)

        # Set up batch and picking.
        Picking = self.env['stock.picking']
        batch = self.create_batch(self.stock_user)
        products_info = [{'product': self.apple, 'qty': 20}]
        test_picking = self.create_picking(picking_type,
                                           origin="test_picking_origin",
                                           products_info=products_info,
                                           batch_id=batch.id,
                                           confirm=True)
        Picking |= test_picking
        products_info = [{'product': self.apple, 'qty': 10}]
        other_picking = self.create_picking(picking_type,
                                            origin="test_picking_origin",
                                            products_info=products_info,
                                            batch_id=batch.id,
                                            confirm=True)
        Picking |= other_picking
        assert len(Picking) == 2
        assert len(batch.picking_ids) == 2
        batch.mark_as_todo()

        # Get moves for later.
        moves = Picking.mapped('move_lines')

        # Reserve stock.
        self.env['stock.picking'].reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(30, int(quant.reserved_quantity))

        picking = moves.mapped('picking_id')
        self.assertTrue(all(x.state == 'assigned' for x in picking))
