# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import UserError

class TestGoodsInPicking(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInPicking, cls).setUpClass()
        Picking = cls.env['stock.picking']
        products_info = [{'product': cls.apple, 'qty': 10}]
        cls.test_picking = cls.create_picking(cls.picking_type_in,
                                              origin="test_picking_origin",
                                              products_info=products_info,
                                              confirm=True)
        cls.SudoPicking = Picking.sudo(cls.inbound_user)
        cls.test_picking = cls.test_picking.sudo(cls.inbound_user)

    def test01_get_pickings_by_package_name_fail(self):
        """ Tests get_pickings by package_name
            when no package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(package_name='DUMMY')
        self.assertEqual(len(returned_pickings), 0)

    def test02_get_pickings_by_package_name_sucess(self):
        """ Tests get_pickings by package_name
            when package exists
        """
        Package = self.env['stock.quant.package']
        test_package = Package.get_package('test_package', create=True)
        self.test_picking.move_line_ids.result_package_id = test_package
        returned_pickings = self.SudoPicking.get_pickings(package_name='test_package')
        self.assertEqual(returned_pickings.id, self.test_picking.id)

    def test03_get_pickings_by_origin_fail(self):
        """ Tests get_pickings by origin
            when no package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(origin='DUMMY')
        self.assertEqual(len(returned_pickings), 0)

    def test04_get_pickings_by_origin_sucess(self):
        """ Tests get_pickings by origin
            when package exists
        """
        returned_pickings = self.SudoPicking.get_pickings(origin=self.test_picking.origin)
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
                    'state',
                    'picking_guidance'
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
        priorities = self.SudoPicking.get_priorities()
        self.assertNotEqual(priorities, [])

    def test08_related_pickings(self):
        """Test first/previous/next picking calculations"""
        pick_a = self.create_picking(self.picking_type_internal)
        move_a1 = self.create_move(self.apple, 1, pick_a)
        pick_b = self.create_picking(self.picking_type_internal)
        move_b1 = self.create_move(self.apple, 1, pick_b)
        move_b1.move_orig_ids = move_a1
        move_b2 = self.create_move(self.apple, 9, pick_b)
        pick_c = self.create_picking(self.picking_type_internal)
        move_c3 = self.create_move(self.apple, 5, pick_c)
        pick_d = self.create_picking(self.picking_type_internal)
        move_d12 = self.create_move(self.apple, 15, pick_d)
        move_d12.move_orig_ids = (move_b1 | move_b2 | move_c3)
        self.assertFalse(pick_a.u_prev_picking_ids)
        self.assertEqual(pick_a.u_next_picking_ids, pick_b)
        self.assertEqual(pick_b.u_prev_picking_ids, pick_a)
        self.assertEqual(pick_b.u_next_picking_ids, pick_d)
        self.assertEqual(pick_d.u_prev_picking_ids, (pick_b | pick_c))
        self.assertFalse(pick_d.u_next_picking_ids)
        self.assertEqual(pick_a.u_first_picking_ids, pick_a)
        self.assertEqual(pick_b.u_first_picking_ids, (pick_a | pick_b))
        self.assertEqual(pick_d.u_first_picking_ids, (pick_a | pick_b | pick_c))
