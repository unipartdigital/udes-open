# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import ValidationError


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

    def test07_update_picking_validate_complete(self):
        """ Test update_picking by addding by splitting a product
            without serial numbers
        """
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 10}]
        self.test_picking.update_picking(products_info=products_info)
        self.assertEqual(self.test_picking.move_lines.quantity_done, 10)
        
        self.test_picking.update_picking(validate=True)
        self.assertEqual(self.test_picking.move_lines.state, 'done')

    
    def test08_update_picking_validate_done_complete_serial_number(self):
        """ Test update_picking by addding by splitting a product
            without serial numbers
        """
        products_info = [{
                            'product_barcode': self.apple.barcode, 
                            'qty': 10, 
                            'serial_numbers': ['Apple1', 'Apple2', 'Apple3', 'Apple4', 'Apple5',
                                               'Apple6', 'Apple7', 'Apple8', 'Apple9', 'Apple10']
                          }] 
        self.test_picking.update_picking(products_info=products_info)
        self.assertEqual(self.test_picking.move_lines.quantity_done, 10)
        
        self.test_picking.update_picking(validate=True)
        self.assertEqual(self.test_picking.move_lines.state, 'done')
        

    def test09_update_picking_split_lanes(self):
        # Without deep copy this will need remaking!
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 5}]
        
        self.test_picking.update_picking(products_info=products_info)
        moves_lines = self.test_picking.move_line_ids
        self.assertEqual(sorted(moves_lines.mapped('qty_done')), sorted([0.0, 5.0]))
        
        self.test_picking.update_picking(products_info=products_info)
        moves_lines = self.test_picking.move_line_ids
        self.assertEqual(sorted(moves_lines.mapped('qty_done')), sorted([5.0, 5.0]))
        
        self.test_picking.update_picking(validate=True)
        self.assertEqual(self.test_picking.move_lines.state, 'done')

    def test10_update_picking_split_lanes_with_serial_number(self):
        products_info = [{
                            'product_barcode': self.apple.barcode, 
                            'qty': 5, 
                            'serial_numbers': ['Apple1', 'Apple2', 'Apple3', 'Apple4', 'Apple5']
                          }]
        self.test_picking.update_picking(products_info=products_info)
        moves_lines = self.test_picking.move_line_ids
        self.assertEqual(sorted(moves_lines.mapped('qty_done')), sorted([0.0, 5.0]))
        
        self.test_picking.update_picking(products_info=products_info)
        moves_lines = self.test_picking.move_line_ids
        self.assertEqual(sorted(moves_lines.mapped('qty_done')), sorted([5.0, 5.0]))
        
        self.test_picking.update_picking(validate=True)
        self.assertEqual(self.test_picking.move_lines.state, 'done')

    def test11_update_picking_incomplete_validate_fail(self):
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 9}]
        self.test_picking.update_picking(products_info=products_info)
        with self.assertRaises(ValidationError) as e:
            self.test_picking.update_picking(validate=True)
        self.assertEqual(e.exception.name, 'Cannot validate transfer because there are move lines todo')
        
    def test12_update_picking_unequal_serial(self):
        self.apple.tracking = "serial"
        products_info = [{
                            'product_barcode': self.apple.barcode,
                            'qty': 5, 
                            'serial_numbers': ['Apple1', 'Apple2', 'Apple3', 'Apple4']
                          }]
        self.test_picking.update_picking(products_info=products_info)
        with self.assertRaises(ValidationError) as e:
            self.test_picking.update_picking(validate=True)
        self.assertEqual(e.exception.name, 'The number of serial numbers and quantity done does not ' \
                                           'match for product Test product Apple')