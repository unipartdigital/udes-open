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
        # create user with security group
        user_params = {
            'name': 'test_user',
            'login': 'test_user_login',
            'group_name': 'inbound',
            'extra_picking_types': cls.picking_type_in,
        }
        cls.test_user = cls.create_user_with_group(**user_params)
        cls.SudoPicking = Picking.sudo(cls.test_user)
        cls.test_picking = cls.test_picking.sudo(cls.test_user)

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
        priorities = self.SudoPicking.get_priorities()
        self.assertNotEqual(priorities, [])
