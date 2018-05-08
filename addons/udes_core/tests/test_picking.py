# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import UserError

class TestGoodsInPicking(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInPicking, cls).setUpClass()
        User = cls.env['res.users']
        PickingType = cls.env['stock.picking.type']
        Picking = cls.env['stock.picking']

        user_warehouse = User.get_user_warehouse()
        # Get goods in type
        in_type_id = user_warehouse.in_type_id
        cls.picking_type_in = PickingType.search([('id', '=', in_type_id.id)])
        # Setting default source location as goods_in doesn't have one
        cls.picking_type_in.default_location_src_id = cls.env.ref('stock.stock_location_suppliers')
        products_info = [{'product': cls.apple, 'qty': 10}]
        cls.test_picking = cls.create_picking(cls.picking_type_in,
                                              origin="test_picking_origin",
                                              products_info=products_info,
                                              confirm=True)

    def test01_get_pickings_by_package_name_fail(self):
        """ Tests get_pickings by package_name
            when no package exists
        """
        Picking = self.env['stock.picking']
        returned_pickings = Picking.get_pickings(package_name='DUMMY')
        self.assertEqual(len(returned_pickings), 0)

    def test02_get_pickings_by_package_name_sucess(self):
        """ Tests get_pickings by package_name
            when package exists
        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']
        test_package = Package.get_package('test_package', create=True)
        self.test_picking.move_line_ids.result_package_id = test_package
        returned_pickings = Picking.get_pickings(package_name='test_package')
        self.assertEqual(returned_pickings.id, self.test_picking.id)

    def test03_get_pickings_by_origin_fail(self):
        """ Tests get_pickings by origin
            when no package exists
        """
        Picking = self.env['stock.picking']
        returned_pickings = Picking.get_pickings(origin='DUMMY')
        self.assertEqual(len(returned_pickings), 0)

    def test04_get_pickings_by_origin_sucess(self):
        """ Tests get_pickings by origin
            when package exists
        """
        Picking = self.env['stock.picking']
        returned_pickings = Picking.get_pickings(origin=self.test_picking.origin)
        self.assertEqual(returned_pickings.id, self.test_picking.id)

    def test05_get_info_all(self):
        """ Tests get_info without requesting
            a field
        """
        info = self.test_picking.get_info()
        expected = ['backorder_id',
                    'id',
                    'location_dest_id',
                    'moves_lines',
                    'name',
                    'origin',
                    'picking_type_id',
                    'priority',
                    'priority_name',
                    'state'
        ]
        # Sorted returns a list(or did when I wrote this)
        # so no need to type cast
        self.assertEqual(sorted(info[0].keys()), sorted(expected))

    def test06_get_info_only_id(self):
        """ Tests get_info requesting a specific field"""
        info = self.test_picking.get_info(fields_to_fetch=['id'])
        # There should only be one and they should all be the same if not
        self.assertEqual(list(info[0].keys()), ['id'])

    def test07_get_priorities(self):
        """ Tests get_priorities by trivially exercising it """
        Picking = self.env['stock.picking']
        priorities = Picking.get_priorities()
        self.assertNotEqual(priorities, [])


class TestHandlePartials(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestHandlePartials, cls).setUpClass()
        Location = cls.env['stock.location']
        User = cls.env['res.users']

        user_warehouse = User.get_user_warehouse()
        # Get goods in type
        cls.picking_type_pick = user_warehouse.pick_type_id
        cls.picking_type_out = user_warehouse.out_type_id

        out_zone = cls.picking_type_pick.default_location_dest_id
        cls.out_location = Location.create({
                'name': "OUT99",
                'barcode': "LTESTOUT99",
                'location_id': out_zone.id,
            })

    def setUp(self):
        """
        Create stock, packages and a picking. Complete one of the moves in the
        picking and check the state of the goods out is what we need for the test.
        """
        super(TestHandlePartials, self).setUp()
        Group = self.env['procurement.group']
        # create stock: 10 apple, 20 bananas, different packs.
        self.create_quant(self.apple.id, self.test_location_01.id, 10, package_id=self.create_package().id)
        self.create_quant(self.banana.id, self.test_location_01.id, 20, package_id=self.create_package().id)

        # Create a picking and validate one of the packages through to Goods Out
        group = Group.get_group("TESTGROUP99", create=True)
        products = [{'product': self.apple, 'qty': 10, 'group_id': group.id},
                    {'product': self.banana, 'qty': 20, 'group_id': group.id},]
        self.pick_picking = self.create_picking(self.picking_type_pick,
                                                products_info=products,
                                                group_id=group.id,
                                                confirm=True, assign=True)
        self.assertEqual(self.pick_picking.state, 'assigned')

        # Complete one move.
        apple_move = self.pick_picking.move_lines.filtered(lambda l: l.product_id == self.apple)
        self.assertEqual(len(apple_move.move_line_ids), 1)
        apple_move.move_line_ids[0].qty_done = apple_move.move_line_ids[0].product_qty
        apple_move.move_line_ids[0].location_dest_id = self.out_location

        # Validate picking, create backorder and check one move remains on the completed picking.
        self.pick_picking.action_done()
        self.assertEqual(self.pick_picking.state, 'done')
        self.assertEqual(len(self.pick_picking.move_lines), 1)
        self.assertEqual(self.pick_picking.move_lines[0], apple_move)

        # Get the out picking, check it's available and has one available and one waiting move.
        self.out_picking = self.pick_picking.mapped('move_lines.move_dest_ids.picking_id')
        self.assertEqual(self.out_picking.state, 'assigned')
        out_move_states = self.out_picking.mapped('move_lines.state')
        self.assertEqual(sorted(out_move_states), sorted(['waiting', 'assigned']))

    def test01_dont_handle_partials(self):
        self.picking_type_out.u_handle_partials = False

        # Pending is set correctly
        self.assertTrue(self.out_picking.u_pending)

        with self.assertRaises(UserError) as e:
            self.out_picking.button_validate()
        self.assertEqual(e.exception.name, 'Cannot validate %s until all of its preceeding pickings are done.' % self.out_picking.name)

        with self.assertRaises(UserError) as f:
            self.out_picking.action_done()
        self.assertEqual(f.exception.name, 'Cannot validate %s until all of its preceeding pickings are done.' % self.out_picking.name)

    def test02_do_handle_partials_button(self):
        self.picking_type_out.u_handle_partials = True

        # Pending is set correctly
        self.assertFalse(self.out_picking.u_pending)

        self.out_picking.button_validate()
        # Test is that an exception has not been raised so assert True.
        self.assertTrue(True)

    def test03_do_handle_partials_action(self):
        self.picking_type_out.u_handle_partials = True

        # Pending is set correctly
        self.assertFalse(self.out_picking.u_pending)

        self.out_picking.action_done()
        # Test is that an exception has not been raised so assert True.
        self.assertTrue(True)