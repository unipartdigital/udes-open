# -*- coding: utf-8 -*-
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
            location_id=cls.picking_type_pick.default_location_src_id.id,
            qty=10.0,
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

        with self.assertRaises(UserError) as e:
            self.test_picking_pick.reserve_stock()

        products = move.product_id.name_get()
        picks = move.picking_id.name
        msg = (
            f"Unable to reserve stock for products {products} for pickings {picks}."
        )
        self.assertEqual(e.exception.args[0], msg)

        self.assertEqual(move.reserved_availability, 0.0)
        self.assertEqual(move.state, "confirmed")
        self.assertEqual(self.test_picking_pick.state, "confirmed")
