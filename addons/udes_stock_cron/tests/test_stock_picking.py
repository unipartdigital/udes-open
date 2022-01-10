# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.addons.udes_stock.tests.common import BaseUDES
from odoo.exceptions import UserError

class TestStockPicking(BaseUDES):
    
    @classmethod
    def setUpClass(cls):
        super(TestStockPicking, cls).setUpClass()

        products_info = [{"product" : cls.apple, "qty" : 10.0}]
        
        # Create a picking with a move
        cls.test_picking_pick = cls.create_picking(
            cls.picking_type_pick,
            products_info=products_info,
            confirm=True,
            location_dest_id=cls.test_received_location_01.id,)
        
        # Create an available quantity of apples
        cls.test_quant_apple = cls.create_quant(
            product_id = cls.apple.id,
            location_id = cls.picking_type_pick.default_location_src_id.id,
            quantity = 10.0
        )

    # Want to inherit the methods from BaseUDES but do not want the database to 
    # rollback after each test, as the method in test: reserve_stock, commits to  
    # the database via the cursor - so will not be able to rollback
    def setUp(cls):
        pass

    def tearDown(cls):
        pass
    
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

    def test01_reserve_available_stock(self):
        # Check there is stock available 
        # Check there is no reserved quantity and that the stock_picking is in state 'confirmed'
        # Run reserve_stock, which should then reserve quantity and change state of stock_picking
        self.assertEqual(self.test_quant_apple.quantity, 10.0)

        Move = self.test_picking_pick.mapped("move_lines").filtered(lambda x: x.name == "Test product Apple")
        self.assertEqual(Move.name, "Test product Apple")
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, 'confirmed')

        self.test_picking_pick.reserve_stock()

        self.assertEqual(Move.reserved_availability, 10.0)
        self.assertEqual(Move.state, 'assigned')
        self.assertEqual(self.test_picking_pick.state, 'assigned')
    
    def test02_reserve_unavailable_stock(self):
        # Check that a stock picking with no stock available cannot reserve stock
        products_info = [{"product" : self.banana, "qty" : 10.0}]
        self.test_picking_pick = self.create_picking(
            self.picking_type_pick,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,)

        Move = self.test_picking_pick.mapped("move_lines").filtered(lambda x: x.name == "Test product Banana")
        self.assertEqual(Move.name, "Test product Banana")
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, 'confirmed')

        with self.assertRaises(UserError):
            self.test_picking_pick.reserve_stock()

        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, 'confirmed')
        self.assertEqual(self.test_picking_pick.state, 'confirmed')
    
    def test03_reserve_partial_stock(self):
        # Turn both u_handle_partials and u_handle_partial_lines flags on
        # Check that stock can be partially reserved 
        products_info = [{"product" : self.banana, "qty" : 10.0}]
        self.test_picking_pick = self.create_picking(
            self.picking_type_pick,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,)
  
        self.test_quant_banana = self.create_quant(
            product_id = self.banana.id,
            location_id = self.picking_type_pick.default_location_src_id.id,
            quantity = 5.0
        )

        Picking_type = self.test_picking_pick.mapped("picking_type_id")
        Picking_type.u_handle_partials = True
        Picking_type.u_handle_partial_lines = True
        self.assertEqual(self.test_picking_pick.mapped("picking_type_id").u_handle_partials, True)
        self.assertEqual(self.test_picking_pick.mapped("picking_type_id").u_handle_partial_lines, True)
        
        Move = self.test_picking_pick.mapped("move_lines").filtered(lambda x: x.name == "Test product Banana")
        self.assertEqual(Move.name, "Test product Banana")
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, 'confirmed')

        self.test_picking_pick.reserve_stock()
    
        self.assertEqual(Move.reserved_availability, 5.0)
        self.assertEqual(Move.state, 'partially_available')
        self.assertEqual(self.test_picking_pick.state, 'assigned')

    def test04_do_not_reserve_partial_stock(self):
        # Turn u_handle_partials flag on adn u_handle_partial_lines off
        # Check that stock can not be partially reserved
        products_info = [{"product" : self.cherry, "qty" : 10.0}]
        self.test_picking_pick = self.create_picking(
            self.picking_type_pick,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,)

        self.test_quant_cherry = self.create_quant(
            product_id = self.cherry.id,
            location_id = self.picking_type_pick.default_location_src_id.id,
            quantity = 5.0
        )

        Picking_type = self.test_picking_pick.mapped("picking_type_id")
        Picking_type.u_handle_partials = True
        Picking_type.u_handle_partial_lines = False
        self.assertEqual(self.test_picking_pick.mapped("picking_type_id").u_handle_partials, True)
        self.assertEqual(self.test_picking_pick.mapped("picking_type_id").u_handle_partial_lines, False)
        
        Move = self.test_picking_pick.mapped("move_lines").filtered(lambda x: x.name == "Test product Cherry")
        self.assertEqual(Move.name, "Test product Cherry")
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, 'confirmed')

        with self.assertRaises(UserError):
            self.test_picking_pick.reserve_stock()
    
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, 'confirmed')
        self.assertEqual(self.test_picking_pick.state, 'confirmed')
    
    def test05_no_partial_transfers(self):
        # u_handle_partials flag is off
        # Check that stock can not be partially reserved
        products_info = [{"product" : self.damson, "qty" : 10.0}]
        
        self.test_picking_pick = self.create_picking(
            self.picking_type_pick,
            products_info=products_info,
            confirm=True,
            location_dest_id=self.test_received_location_01.id,)

        self.test_quant_damson = self.create_quant(
            product_id = self.damson.id,
            location_id = self.picking_type_pick.default_location_src_id.id,
            quantity = 5.0
        )

        Picking_type = self.test_picking_pick.mapped("picking_type_id")
        Picking_type.u_handle_partials = False
        Picking_type.u_handle_partial_lines = False
        self.assertEqual(self.test_picking_pick.mapped("picking_type_id").u_handle_partials, False)
        self.assertEqual(self.test_picking_pick.mapped("picking_type_id").u_handle_partial_lines, False)

        Move = self.test_picking_pick.mapped("move_lines").filtered(lambda x: x.name == "Test product Damson")
        self.assertEqual(Move.name, "Test product Damson")
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, 'confirmed')

        with self.assertRaises(UserError):
            self.test_picking_pick.reserve_stock()
    
        self.assertEqual(Move.reserved_availability, 0.0)
        self.assertEqual(Move.state, 'confirmed')
        self.assertEqual(self.test_picking_pick.state, 'confirmed')
