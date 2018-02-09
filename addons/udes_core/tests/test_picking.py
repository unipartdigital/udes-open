# -*- coding: utf-8 -*-

from . import common


class TestGoodsInPicking(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInPicking, cls).setUpClass()
        User = cls.env['res.users']
        PickingType = cls.env['stock.picking.type']
        Picking = cls.env['stock.picking']
        Package = cls.env['stock.quant.package']

        user_warehouse = User.get_user_warehouse()
        # Get goods in type
        in_type_id = user_warehouse.in_type_id
        cls.picking_type_in = PickingType.search([('id', '=', in_type_id.id)])
        # Setting default source location as goods_in doesn't have one
        cls.picking_type_in.default_location_src_id = cls.env.ref('stock.stock_location_suppliers')
        cls.test_picking = cls.create_picking(cls.picking_type_in, origin="test_picking_origin")
        cls.test_move = cls.create_move(cls.apple, 10, cls.test_picking)
        cls.test_picking.action_confirm()
        cls.test_package = Package.get_package("test_package", create=True)
        cls.test_move.move_line_ids.result_package_id = cls.test_package


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
        returned_pickings = Picking.get_pickings(package_name=self.test_package.name)
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
        """ Tests get_info with requesting
            a field
        """
        info = self.test_picking.get_info()
        # This has been pre-sorted
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
        self.assertEqual(sorted(info[0].keys()), expected)
    
    def test06_get_info_only_id(self):
        """ Tests get_info requesting a specific field"""
        info = self.test_picking.get_info(fields_to_fetch=['id'])
        # There should only be one and they should all be the same if not
        self.assertEqual(list(info[0].keys()), ['id'])
        # Another way would be 
        # self.assertEqual(len(info[0].keys()), 1)
        # self.assertTrue('id' in info[0].keys())
