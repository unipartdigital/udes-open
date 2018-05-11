# -*- coding: utf-8 -*-

from odoo.addons.udes_core.tests import common
from odoo.exceptions import UserError


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
        self.create_quant(self.apple.id, self.test_location_01.id, 10,
                          package_id=self.create_package().id)
        self.create_quant(self.banana.id, self.test_location_01.id, 20,
                          package_id=self.create_package().id)

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
        self.assertEqual(e.exception.name,
                         'Cannot validate %s until all of its preceding'
                         ' pickings are done.' % self.out_picking.name)

        with self.assertRaises(UserError) as f:
            self.out_picking.action_done()
        self.assertEqual(f.exception.name,
                         'Cannot validate %s until all of its preceding'
                         ' pickings are done.' % self.out_picking.name)

    def test02_do_handle_partials_button(self):
        self.picking_type_out.u_handle_partials = True

        # Pending is set correctly
        self.assertFalse(self.out_picking.u_pending)

        self.out_picking.button_validate()
    def test03_do_handle_partials_action(self):
        self.picking_type_out.u_handle_partials = True

        # Pending is set correctly
        self.assertFalse(self.out_picking.u_pending)

        self.out_picking.action_done()

    def test04_dont_handle_partials_canceled(self):
        self.picking_type_out.u_handle_partials = False

        # Pending is set correctly
        self.assertTrue(self.out_picking.u_pending)

        with self.assertRaises(UserError) as e:
            self.out_picking.button_validate()
        self.assertEqual(e.exception.name,
                         'Cannot validate %s until all of its preceding'
                         ' pickings are done.' % self.out_picking.name)

        with self.assertRaises(UserError) as f:
            self.out_picking.action_done()
        self.assertEqual(f.exception.name,
                         'Cannot validate %s until all of its preceding'
                         ' pickings are done.' % self.out_picking.name)

        prev_undone_pickings = self.out_picking.u_prev_picking_ids.filtered(
            lambda p: p.state != 'done')

        prev_undone_pickings.action_cancel()
        self.out_picking.action_done()
