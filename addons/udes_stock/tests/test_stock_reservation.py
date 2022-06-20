"""
Tests for StockPicking.reserve_stock.

The method itself cannot be tested because it contains a commit statement, but
we can test related methods.
"""
from .common import BaseUDES


class FindUnreservableMovesTestCase(BaseUDES):
    """Test cases for StockPicking._find_unfulfillable_moves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_quant(cls.apple.id, cls.test_location_01.id, 10)

    def test_does_not_report_moves_if_stock_is_available(self):
        """The system will not report moves if there is enough stock to reserve."""
        self.picking_type_pick.u_handle_partials = False
        products_info = [{"product": self.apple, "qty": 10}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)

        unreservable_moves = picking._find_unfulfillable_moves()

        self.assertFalse(unreservable_moves)

    def test_reports_moves_if_stock_is_not_available(self):
        """The system will report moves for which there is insufficient stock."""
        self.picking_type_pick.u_handle_partials = False
        products_info = [{"product": self.banana, "qty": 10}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)

        unreservable_moves = picking._find_unfulfillable_moves()

        self.assertEqual(unreservable_moves, picking.move_lines)

    def test_ignores_cancelled_moves(self):
        """The system will disregard moves which are cancelled when reporting."""
        # The same logic applies to assigned and done states.
        self.picking_type_pick.u_handle_partials = False
        products_info = [{"product": self.apple, "qty": 10}, {"product": self.banana, "qty": 10}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)
        move = picking.move_lines.filtered(lambda m: m.product_id == self.banana)
        move._action_cancel()

        unreservable_moves = picking._find_unfulfillable_moves()

        self.assertFalse(unreservable_moves)

    def test_allows_partially_fulfilled_lines_if_handle_partials_is_on(self):
        """The system will not report partially reserved moves if u_handle_partials is True."""
        self.picking_type_pick.u_handle_partials = True
        products_info = [{"product": self.apple, "qty": 15}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)

        unreservable_moves = picking._find_unfulfillable_moves()

        self.assertFalse(unreservable_moves)

    def test_prohibits_partially_fulfilled_lines_if_handle_partials_is_off(self):
        """The system will report partially reservable moves if u_handle_partials is False."""
        self.picking_type_pick.u_handle_partials = False
        products_info = [{"product": self.apple, "qty": 15}]
        picking = self.create_picking(self.picking_type_pick, products_info, confirm=True)

        unreservable_moves = picking._find_unfulfillable_moves()

        self.assertEqual(unreservable_moves, picking.move_lines)
