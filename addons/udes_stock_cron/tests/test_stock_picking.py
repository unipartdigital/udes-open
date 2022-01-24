# -*- coding: utf-8 -*-
from odoo.addons.udes_stock.tests.common import BaseUDES
from odoo.exceptions import UserError
from odoo.tests import get_db_name
import odoo


class TestStockPicking(BaseUDES):
    @classmethod
    def setUpClass(cls):
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
            quantity=10.0,
        )

    @classmethod
    def tearDownClass(cls):
        super(TestStockPicking, cls).tearDownClass()
        cls.registry.leave_test_mode()

    # Want to inherit the methods from BaseUDES but do not want the database to
    # rollback after each test, as the method in test: reserve_stock, commits to
    # the database via the cursor - so will not be able to rollback
    # def setUp(cls):
    #     pass

    # def tearDown(cls):
    #     pass

    @classmethod
    def create_quant(self, product_id, location_id, quantity, **kwargs):
        """
        Purpose: Format the stock quant information and pass it to stock.quant for
        creation.
        Params: recordset id, recordset id, float -> stock.quant recordset
        """
        Quant = self.env["stock.quant"]
        vals = {
            "product_id": product_id,
            "location_id": location_id,
            "quantity": quantity,
        }
        return Quant.create(vals, **kwargs)

    def test_reserve_available_stock(self):
        # Check there is stock available
        # Check there is no reserved quantity and that the stock_picking is in state 'confirmed'
        # Run reserve_stock, which should then reserve quantity and change state of stock_picking
        self.assertEqual(self.test_quant_apple.quantity, 10.0)

        Move = self.test_picking_pick.move_lines.filtered(
            lambda m: m.name == "Test product Apple"
        )
        self.assertEqual(Move.name, "Test product Apple")
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, "confirmed")

        self.test_picking_pick.reserve_stock()

        self.assertEqual(Move.reserved_availability, 10.0)
        self.assertEqual(Move.state, "assigned")
        self.assertEqual(self.test_picking_pick.state, "assigned")

    def test_reserve_unavailable_stock(self):
        # Check that a stock picking with no stock available cannot reserve stock
        products_info = [{"product": self.banana, "uom_qty": 10.0}]
        self.test_picking_pick = self.create_picking(
            self.picking_type_pick,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,
        )

        Move = self.test_picking_pick.move_lines.filtered(
            lambda m: m.name == "Test product Banana"
        )
        self.assertEqual(Move.name, "Test product Banana")
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, "confirmed")

        with self.assertRaises(UserError):
            self.test_picking_pick.reserve_stock()

        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, "confirmed")
        self.assertEqual(self.test_picking_pick.state, "confirmed")
