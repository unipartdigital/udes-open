# -*- coding: utf-8 -*-

from odoo.addons.udes_core.tests import common
from odoo.exceptions import ValidationError
from collections import Counter

class TestGoodsInTargetStorageTypes(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInTargetStorageTypes, cls).setUpClass()
        User = cls.env['res.users']
        user_warehouse = User.get_user_warehouse()
        # Get goods in type
        cls.picking_type_in = user_warehouse.in_type_id
        # Setting default source location as goods_in doesn't have one
        cls.picking_type_in.default_location_src_id = cls.env.ref('stock.stock_location_suppliers')

    def validate_move_lines(self, move_lines, product, ordered_qty, qty_done, is_package=False,
                            is_pallet=False, package_name=False, serial_numbers=False):
        """ Validates move lines based on the inputs"""

        self.assertTrue(len(move_lines) > 0)
        self.assertEqual(move_lines.mapped('product_id'), product)
        self.assertEqual(sum(move_lines.mapped('qty_done')), qty_done)
        self.assertEqual(sum(move_lines.mapped('ordered_qty')), ordered_qty)

        if serial_numbers:
            self.assertEqual(sorted(move_lines.mapped('lot_name')), sorted(serial_numbers))

        if is_pallet and not package_name:
            # In case the person writting the test forgets package_name
            raise ValueError('Missing package_name')

        if package_name and is_package and is_pallet:
            # pallet of packages
            self.assertTrue(all(ml.picking_id.picking_type_id.u_target_storage_format == 'pallet_packages' \
                                for ml in move_lines))
            self.assertTrue(all(ml.result_package_id is not False for ml in move_lines))
            self.assertTrue(all(ml.u_result_parent_package_id.name == package_name for ml in move_lines))
        elif package_name and is_pallet:
            # pallet of products
            self.assertTrue(all(ml.picking_id.picking_type_id.u_target_storage_format == 'pallet_products' \
                                for ml in move_lines))
            self.assertTrue(all(ml.result_package_id.name == package_name for ml in move_lines))
            self.assertTrue(all(ml.u_result_parent_package_id.name == False for ml in move_lines))
        elif is_package:
            # package
            self.assertTrue(all(ml.picking_id.picking_type_id.u_target_storage_format == 'package' \
                                for ml in move_lines))
            if package_name:
                self.assertTrue(all(ml.result_package_id.name == package_name for ml in move_lines))
            else:
                self.assertTrue(all(ml.result_package_id is not False for ml in move_lines))
            self.assertTrue(all(ml.u_result_parent_package_id.name == False for ml in move_lines))
        else:
            # products
            if qty_done > 0: # only need to check picking type when we have done something
                self.assertTrue(all(ml.picking_id.picking_type_id.u_target_storage_format == 'product' \
                                    for ml in move_lines))
            self.assertTrue(all(ml.result_package_id.name == False for ml in move_lines))
            self.assertTrue(all(ml.u_result_parent_package_id.name == False for ml in move_lines))

    def validate_quants(self, quants=None, package=None, expected_quants=None, is_pallet=False, is_package=False,
                        num_packages_expected=None, expected_location=None):
        """ Check that quants are as expected """
        self.assertTrue((quants is not None) ^ (package is not None))
        self.assertTrue(expected_quants is not None)
        self.assertTrue(expected_location is not None)

        if package is not None:
            quants = package._get_contained_quants()
            if is_pallet:
                self.assertTrue(len(package.children_quant_ids) > 0)
            # XOR
            if is_package ^ is_pallet:
                self.assertTrue(len(package.quant_ids) > 0)
            elif is_pallet and is_package:
                self.assertEqual(len(package.quant_ids), 0)

                self.assertTrue(num_packages_expected is not None)
                self.assertEqual(len(package.children_ids), num_packages_expected)

        self.assertTrue(len(quants) > 0)
        self.assertTrue(all(qnt.location_id == expected_location for qnt in quants))
        # Check total number of quants
        self.assertEqual(len(quants), len(expected_quants))

        # Check number of quants by product and qty
        for expected, num_expected in Counter(map(lambda x: tuple(x.items()), expected_quants)).items():
            expected = dict(expected)
            # Filter by product and qty
            quant = quants.filtered(lambda x: x.product_id == expected['product'] and x.quantity == expected['qty'])
            self.assertTrue(quant, 'expected quant was not found')
            # Check that the number of quants are the number expected
            self.assertEqual(len(quant), num_expected, 'some quants are missing')

    def test01_target_storage_format_product(self):
        """ Test for basic usage of target_storage_format product"""
        Package = self.env['stock.quant.package']
        Quants = self.env['stock.quant']
        package = Package.get_package('test_package', create=True)

        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        self.picking_type_in.u_target_storage_format = 'product'
        self.validate_move_lines(picking.move_line_ids, self.apple, 4, 0)
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.assertEqual(e.exception.name, 'Invalid parameters for products target'
                                           ' storage format.',
                         'No/Incorrect error message was thrown')
        picking.update_picking(products_info=products_info)
        self.validate_move_lines(picking.move_line_ids, self.apple, 4, 4)
        picking.update_picking(validate=True)
        qnt_domain = [
                        ('product_id','=', self.apple.id),
                        ('location_id', '=', self.picking_type_in.default_location_dest_id.id),
                     ]
        qnts = Quants.search(qnt_domain)
        validation_args = {'expected_location': self.picking_type_in.default_location_dest_id}
        expected_quants = [{'product': self.apple, 'qty': 4}]
        self.validate_quants(quants=qnts, expected_quants=expected_quants, **validation_args)

    def test02_target_storage_format_package(self):
        """ Test for basic usage of target_storage_format package"""
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_package': True
                          }
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        self.picking_type_in.u_target_storage_format = 'package'

        self.validate_move_lines(picking.move_line_ids, self.apple, 4, 0)
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(picking.move_line_ids, self.apple, 4, 4, package_name=package.name,
                                 **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants = [{'product': self.apple, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test03_target_storage_format_pallet_products(self):
        """ Test for basic usage of target_storage_format
            pallet_products
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_pallet': True,
                          }
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        self.picking_type_in.u_target_storage_format = 'pallet_products'

        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)
        self.assertEqual(e.exception.name, 'Invalid parameters for target storage format,'
                                           ' expecting result package.',
                         'No/Incorrect error message was thrown')

        picking.update_picking(products_info=products_info, result_package_name='test_package')
        self.validate_move_lines(picking.move_line_ids, self.apple, 4, 4,
                                 package_name='test_package', **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants = [{'product': self.apple, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test04_target_storage_format_pallet_packages(self):
        """ Test for basic usage of target_storage_format
            pallet_packages
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_pallet': True,
                            'is_package': True
                          }
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        self.picking_type_in.u_target_storage_format = 'pallet_packages'

        self.validate_move_lines(picking.move_line_ids, self.apple, 4, 0)
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)
        self.assertEqual(e.exception.name, 'Invalid parameters for target storage format,'
                                           ' expecting result package.',
                         'No/Incorrect error message was thrown')
        picking.update_picking(products_info=products_info, result_package_name='test_package')
        self.validate_move_lines(picking.move_line_ids, self.apple, 4, 4,
                                 package_name='test_package', **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({
                                    'num_packages_expected': 1,
                                    'expected_location': self.picking_type_in.default_location_dest_id,
                                })
        expected_quants = [{'product': self.apple, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test05_target_storage_format_package_over_receive_product(self):
        """Tests over receiving for target_storage_format product"""
        Quants = self.env['stock.quant']
        create_info = [{'product': self.apple, 'qty': 2}]
        self.picking_type_in.u_over_receive = True
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        self.validate_move_lines(picking.move_line_ids, self.apple, 2, 0)
        self.picking_type_in.u_target_storage_format = 'product'
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        picking.update_picking(products_info=products_info)
        self.validate_move_lines(picking.move_line_ids, self.apple, 2, 4)
        picking.update_picking(validate=True)
        qnt_domain = [
                       ('product_id','=', self.apple.id),
                       ('location_id', '=', self.picking_type_in.default_location_dest_id.id),
                     ]
        qnts = Quants.search(qnt_domain)

        validation_args = {'expected_location': self.picking_type_in.default_location_dest_id}
        expected_quants = [{'product': self.apple, 'qty': 4}]
        self.validate_quants(quants=qnts, expected_quants=expected_quants, **validation_args)

    def test06_target_storage_format_package_over_receive_package(self):
        """Tests over receiving for target_storage_format package"""
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_package': True
                          }
        self.picking_type_in.u_over_receive = True
        create_info = [{'product': self.apple, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        self.validate_move_lines(picking.move_line_ids, self.apple, 2, 0)
        self.picking_type_in.u_target_storage_format = 'package'
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(picking.move_line_ids, self.apple, 2, 4,
                                 package_name=package.name, **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants = [{'product': self.apple, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)


    def test07_target_storage_format_package_over_receive_pallet_products(self):
        """Tests over receiving for target_storage_format
           pallet_products
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_pallet': True,
                          }
        self.picking_type_in.u_over_receive = True
        create_info = [{'product': self.apple, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        self.validate_move_lines(picking.move_line_ids, self.apple, 2, 0)
        self.picking_type_in.u_target_storage_format = 'pallet_products'
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(picking.move_line_ids, self.apple, 2, 4,
                                 is_pallet=True, package_name=package.name)
        picking.update_picking(validate=True)
        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants = [{'product': self.apple, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test08_target_storage_format_package_over_receive_pallet_packages(self):
        """Tests over receiving for target_storage_format
           pallet_packages
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_pallet': True,
                            'is_package': True
                          }
        self.picking_type_in.u_over_receive = True
        create_info = [{'product': self.apple, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        self.validate_move_lines(picking.move_line_ids, self.apple, 2, 0)
        self.picking_type_in.u_target_storage_format = 'pallet_packages'
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(picking.move_line_ids, self.apple, 2, 4,
                                 package_name=package.name, **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({
                                    'num_packages_expected': 1,
                                    'expected_location': self.picking_type_in.default_location_dest_id
                                })
        expected_quants = [{'product': self.apple, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)


    def test09_target_storage_format_package_serial_numbers_product(self):
        """Tests receiving tracked products for
           target_storage_format product
        """
        Quants = self.env['stock.quant']
        create_info = [{'product': self.strawberry, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        strawberry_sn = ['Strawberry0', 'Strawberry1']
        products_info = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 2,
                            'serial_numbers': strawberry_sn
                        }]


        self.picking_type_in.u_target_storage_format = 'product'
        self.validate_move_lines(picking.move_line_ids, self.strawberry, 2, 0)
        picking.update_picking(products_info=products_info)
        self.validate_move_lines(picking.move_line_ids, self.strawberry, 2, 2,
                                 serial_numbers=strawberry_sn)
        picking.update_picking(validate=True)
        validation_args = {'expected_location': self.picking_type_in.default_location_dest_id}
        qnt_domain = [
                        ('product_id','=', self.strawberry.id),
                        ('location_id', '=', self.picking_type_in.default_location_dest_id.id),
                     ]
        qnts = Quants.search(qnt_domain)
        expected_quants = [{'product': self.strawberry, 'qty': 1}, {'product': self.strawberry, 'qty': 1}]
        self.validate_quants(quants=qnts, expected_quants=expected_quants, **validation_args)

    def test10_target_storage_format_package_serial_numbers_package(self):
        """Tests receiving tracked products for
           target_storage_format package
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_package': True
                          }
        create_info = [{'product': self.strawberry, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        strawberry_sn = ['Strawberry0', 'Strawberry1']
        products_info = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 2,
                            'serial_numbers': strawberry_sn
                        }]
        self.picking_type_in.u_target_storage_format = 'package'
        self.validate_move_lines(picking.move_line_ids, self.strawberry, 2, 0)
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(picking.move_line_ids, self.strawberry, 2, 2,
                                 serial_numbers=strawberry_sn, package_name=package.name,
                                 **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants = [{'product': self.strawberry, 'qty': 1}, {'product': self.strawberry, 'qty': 1}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test11_target_storage_format_package_serial_numbers_pallet_products(self):
        """Tests receiving tracked products for
           target_storage_format pallet_products
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_pallet': True,
                          }
        create_info = [{'product': self.strawberry, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        strawberry_sn = ['Strawberry0', 'Strawberry1']
        products_info = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 2,
                            'serial_numbers': strawberry_sn
                        }]
        self.picking_type_in.u_target_storage_format = 'pallet_products'
        self.validate_move_lines(picking.move_line_ids, self.strawberry, 2, 0)
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(picking.move_line_ids, self.strawberry, 2, 2,
                                 serial_numbers=strawberry_sn, package_name=package.name,
                                 **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants = [{'product': self.strawberry, 'qty': 1}, {'product': self.strawberry, 'qty': 1}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)


    def test12_target_storage_format_package_serial_numbers_pallet_packages(self):
        """Tests receiving tracked products for
           target_storage_format pallet_packages
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_pallet': True,
                            'is_package': True
                          }
        create_info = [{'product': self.strawberry, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        strawberry_sn = ['Strawberry0', 'Strawberry1']
        products_info = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 2,
                            'serial_numbers': strawberry_sn
                        }]
        self.picking_type_in.u_target_storage_format = 'pallet_packages'
        self.validate_move_lines(picking.move_line_ids, self.strawberry, 2, 0)
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(picking.move_line_ids, self.strawberry, 2, 2,
                                 serial_numbers=strawberry_sn, package_name=package.name,
                                 **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({
                                    'num_packages_expected': 1,
                                    'expected_location': self.picking_type_in.default_location_dest_id
                                })
        expected_quants = [{'product': self.strawberry, 'qty': 1}, {'product': self.strawberry, 'qty': 1}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test13_target_storage_format_mixed_product(self):
        """Tests receiving mixed products for
           target_storage_format product
        """
        Quants = self.env['stock.quant']
        create_info = [{'product': self.apple, 'qty': 4},
                       {'product': self.banana, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)


        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        banana_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana)
        self.validate_move_lines(apple_move_lines, self.apple, 4, 0)
        self.validate_move_lines(banana_move_lines, self.banana, 4, 0)
        products_info = [
                         {'product_barcode': self.apple.barcode, 'qty': 4},
                         {'product_barcode': self.banana.barcode, 'qty': 4},
                        ]
        self.picking_type_in.u_target_storage_format = 'product'
        picking.update_picking(products_info=products_info)
        self.validate_move_lines(apple_move_lines, self.apple, 4, 4)
        self.validate_move_lines(banana_move_lines, self.banana, 4, 4)
        picking.update_picking(validate=True)

        validation_args = {'expected_location': self.picking_type_in.default_location_dest_id}
        expected_quants = [{'product': self.apple, 'qty': 4}, {'product': self.banana, 'qty': 4}]
        qnt_domain = [
                        ('location_id', '=', self.picking_type_in.default_location_dest_id.id),
                        '|',
                        ('product_id','=', self.apple.id),
                        ('product_id','=', self.banana.id)
                      ]
        qnts = Quants.search(qnt_domain)
        self.validate_quants(quants=qnts, expected_quants=expected_quants, **validation_args)

    def test14_target_storage_format_mixed_package(self):
        """Tests receiving mixed products for
           target_storage_format package
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_package': True
                          }
        create_info = [{'product': self.apple, 'qty': 4},
                       {'product': self.banana, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        banana_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana)
        self.validate_move_lines(apple_move_lines, self.apple, 4, 0)
        self.validate_move_lines(banana_move_lines, self.banana, 4, 0)
        products_info = [
                         {'product_barcode': self.apple.barcode, 'qty': 4},
                         {'product_barcode': self.banana.barcode, 'qty': 4},
                        ]
        self.picking_type_in.u_target_storage_format = 'package'
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(apple_move_lines, self.apple, 4, 4,
                                 package_name=package.name, **validation_args)
        self.validate_move_lines(banana_move_lines, self.banana, 4, 4,
                                 package_name=package.name, **validation_args)
        picking.update_picking(validate=True)

        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants = [{'product': self.apple, 'qty': 4}, {'product': self.banana, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test15_target_storage_format_mixed_pallet_products(self):
        """Tests receiving mixed products for
           target_storage_format pallet_products
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_pallet': True,
                          }
        create_info = [{'product': self.apple, 'qty': 4},
                       {'product': self.banana, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        banana_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana)
        self.validate_move_lines(apple_move_lines, self.apple, 4, 0)
        self.validate_move_lines(banana_move_lines, self.banana, 4, 0)
        products_info = [
                         {'product_barcode': self.apple.barcode, 'qty': 4},
                         {'product_barcode': self.banana.barcode, 'qty': 4},
                        ]
        self.picking_type_in.u_target_storage_format = 'pallet_products'
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(apple_move_lines, self.apple, 4, 4,
                                 package_name=package.name, **validation_args)
        self.validate_move_lines(banana_move_lines, self.banana, 4, 4,
                                 package_name=package.name, **validation_args)
        picking.update_picking(validate=True)

        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants = [{'product': self.apple, 'qty': 4}, {'product': self.banana, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test16_target_storage_format_mixed_pallet_packages(self):
        """Tests receiving mixed products for
           target_storage_format pallet_packages
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)
        validation_args = {
                            'is_pallet': True,
                            'is_package': True
                          }
        create_info = [{'product': self.apple, 'qty': 4},
                       {'product': self.banana, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        banana_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana)
        self.validate_move_lines(apple_move_lines, self.apple, 4, 0)
        self.validate_move_lines(banana_move_lines, self.banana, 4, 0)
        products_info = [
                         {'product_barcode': self.apple.barcode, 'qty': 4},
                         {'product_barcode': self.banana.barcode, 'qty': 4},
                        ]
        self.picking_type_in.u_target_storage_format = 'pallet_packages'
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.validate_move_lines(apple_move_lines, self.apple, 4, 4,
                                 package_name=package.name, **validation_args)
        self.validate_move_lines(banana_move_lines, self.banana, 4, 4,
                                 package_name=package.name, **validation_args)
        picking.update_picking(validate=True)

        validation_args.update({
                                    'num_packages_expected': 1,
                                    'expected_location': self.picking_type_in.default_location_dest_id
                                })
        expected_quants = [{'product': self.apple, 'qty': 4}, {'product': self.banana, 'qty': 4}]
        self.validate_quants(package=package, expected_quants=expected_quants, **validation_args)

    def test17_target_storage_format_multiple_packages_from_same_product_package(self):
        """Tests that mutiple sets of the same product
           can be made from a single picking for
           target_storage_format package.
        """
        Package = self.env['stock.quant.package']
        package1 = Package.get_package('test_package1', create=True)
        package2 = Package.get_package('test_package2', create=True)
        validation_args = {
                            'is_package': True
                          }

        create_info = [{'product': self.apple, 'qty': 5}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info1 = [{'product_barcode': self.apple.barcode, 'qty': 2}]
        products_info2 = [{'product_barcode': self.apple.barcode, 'qty': 3}]
        self.validate_move_lines(picking.move_line_ids, self.apple, 5, 0)

        self.picking_type_in.u_target_storage_format = 'package'
        picking.update_picking(products_info=products_info1, result_package_name=package1.name)
        apple_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        self.validate_move_lines(apple_lines_done, self.apple, 2, 2, package_name=package1.name, **validation_args)

        picking.update_picking(products_info=products_info2, result_package_name=package2.name)
        apple_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        apple_lines_done2 -= apple_lines_done
        self.validate_move_lines(apple_lines_done2, self.apple, 3, 3, package_name=package2.name, **validation_args)
        picking.update_picking(validate=True)

        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants1 = [{'product': self.apple, 'qty': 2}]
        expected_quants2 = [{'product': self.apple, 'qty': 3}]
        self.validate_quants(package=package1, expected_quants=expected_quants1, **validation_args)
        self.validate_quants(package=package2, expected_quants=expected_quants2, **validation_args)

    def test18_target_storage_format_multiple_packages_from_same_product_pallet_products(self):
        """Tests that mutiple sets of the same product
           can be made from a single picking for
           target_storage_format pallet_products.
        """
        # Two packages from same product
        Package = self.env['stock.quant.package']
        package1 = Package.get_package('test_package1', create=True)
        package2 = Package.get_package('test_package2', create=True)
        validation_args = {
                            'is_pallet': True,
                          }

        validation_args = {'is_pallet': True}

        create_info = [{'product': self.apple, 'qty': 5}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info1 = [{'product_barcode': self.apple.barcode, 'qty': 2}]
        products_info2 = [{'product_barcode': self.apple.barcode, 'qty': 3}]
        self.validate_move_lines(picking.move_line_ids, self.apple, 5, 0)

        self.picking_type_in.u_target_storage_format = 'pallet_products'
        picking.update_picking(products_info=products_info1, result_package_name=package1.name)
        apple_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        self.validate_move_lines(apple_lines_done, self.apple, 2, 2,
                                 package_name=package1.name, **validation_args)

        picking.update_picking(products_info=products_info2, result_package_name=package2.name)
        apple_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        apple_lines_done2 -= apple_lines_done
        self.validate_move_lines(apple_lines_done2, self.apple, 3, 3,
                                 package_name=package2.name, **validation_args)
        picking.update_picking(validate=True)

        validation_args.update({'expected_location': self.picking_type_in.default_location_dest_id})
        expected_quants1 = [{'product': self.apple, 'qty': 2}]
        expected_quants2 = [{'product': self.apple, 'qty': 3}]
        self.validate_quants(package=package1, expected_quants=expected_quants1, **validation_args)
        self.validate_quants(package=package2, expected_quants=expected_quants2, **validation_args)

    def test19_target_storage_format_multiple_packages_from_same_product_pallet_packages(self):
        """Tests that mutiple sets of the two products
           can be made from a single picking
           with two packages on same pallet
           for target_storage_format pallet_packages.
        """
        # Two packages from same product
        Package = self.env['stock.quant.package']
        package1 = Package.get_package('test_package1', create=True)

        validation_args = {
                            'is_pallet': True,
                            'is_package': True
                          }

        create_info = [{'product': self.apple, 'qty': 5}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info1 = [{'product_barcode': self.apple.barcode, 'qty': 2}]
        products_info2 = [{'product_barcode': self.apple.barcode, 'qty': 3}]
        self.validate_move_lines(picking.move_line_ids, self.apple, 5, 0)

        self.picking_type_in.u_target_storage_format = 'pallet_packages'
        picking.update_picking(products_info=products_info1, result_package_name=package1.name)
        apple_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        self.validate_move_lines(apple_lines_done, self.apple, 2, 2,
                                 package_name=package1.name,
                                 **validation_args)

        picking.update_picking(products_info=products_info2, result_package_name=package1.name)
        apple_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        apple_lines_done2 -= apple_lines_done
        self.validate_move_lines(apple_lines_done2, self.apple, 3, 3,
                                 package_name=package1.name,
                                 **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({
                                    'num_packages_expected': 2,
                                    'expected_location': self.picking_type_in.default_location_dest_id,
                                })
        expected_quants = [{'product': self.apple, 'qty': 2}, {'product': self.apple, 'qty': 3}]
        self.validate_quants(package=package1, expected_quants=expected_quants, **validation_args)

    def test20_target_storage_format_multiple_pallets_from_same_product_pallet_packages(self):
        """Tests that mutiple sets of the two products
           can be made from a single picking
           with a single package per pallet
           for target_storage_format pallet_packages.
        """
        # Two packages from same product
        Package = self.env['stock.quant.package']
        package1 = Package.get_package('test_package1', create=True)
        package2 = Package.get_package('test_package2', create=True)

        validation_args = {
                            'is_pallet': True,
                            'is_package': True
                          }

        create_info = [{'product': self.apple, 'qty': 5}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info1 = [{'product_barcode': self.apple.barcode, 'qty': 2}]
        products_info2 = [{'product_barcode': self.apple.barcode, 'qty': 3}]
        self.validate_move_lines(picking.move_line_ids, self.apple, 5, 0)

        self.picking_type_in.u_target_storage_format = 'pallet_packages'
        picking.update_picking(products_info=products_info1, result_package_name=package1.name)
        apple_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        self.validate_move_lines(apple_lines_done,
                                 self.apple, 2, 2,
                                 package_name=package1.name,
                                 **validation_args
                                 )

        picking.update_picking(products_info=products_info2, result_package_name=package2.name)
        apple_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        apple_lines_done2 -= apple_lines_done
        self.validate_move_lines(apple_lines_done2,
                                 self.apple, 3, 3,
                                 package_name=package2.name,
                                 **validation_args
                                 )

        picking.update_picking(validate=True)
        validation_args.update({
                                    'num_packages_expected': 1,
                                    'expected_location': self.picking_type_in.default_location_dest_id,
                                })

        expected_quants1 = [{'product': self.apple, 'qty': 2}]
        expected_quants2 = [{'product': self.apple, 'qty': 3}]
        self.validate_quants(package=package1, expected_quants=expected_quants1, **validation_args)
        self.validate_quants(package=package2, expected_quants=expected_quants2, **validation_args)

    def test21_target_storage_format_multiple_mixed_packages_from_two_products_package(self):
        """Tests that mutiple sets of the two products
           can be made from a single picking
           for target_storage_format package.
        """
        Package = self.env['stock.quant.package']
        package1 = Package.get_package('test_package1', create=True)
        package2 = Package.get_package('test_package2', create=True)
        validation_args = {
                            'is_package': True
                          }
        create_info = [
                        {'product': self.apple, 'qty': 5},
                        {'product': self.banana, 'qty': 5},
                      ]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info1 = [
                           {'product_barcode': self.apple.barcode, 'qty': 2},
                           {'product_barcode': self.banana.barcode, 'qty': 2},
                         ]
        products_info2 = [
                           {'product_barcode': self.apple.barcode, 'qty': 3},
                           {'product_barcode': self.banana.barcode, 'qty': 3},
                         ]

        self.picking_type_in.u_target_storage_format = 'package'

        apple_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        banana_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana)
        self.validate_move_lines(apple_lines, self.apple, 5, 0)
        self.validate_move_lines(banana_lines, self.banana, 5, 0)

        picking.update_picking(products_info=products_info1, result_package_name=package1.name)
        apple_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        banana_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana and x.qty_done > 0)
        self.validate_move_lines(apple_lines_done, self.apple, 2, 2, package_name=package1.name, **validation_args)
        self.validate_move_lines(banana_lines_done, self.banana, 2, 2, package_name=package1.name, **validation_args)

        picking.update_picking(products_info=products_info2, result_package_name=package2.name)
        apple_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        banana_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana and x.qty_done > 0)
        apple_lines_done2 -= apple_lines_done
        banana_lines_done2 -= banana_lines_done
        self.validate_move_lines(apple_lines_done2, self.apple, 3, 3, package_name=package2.name, **validation_args)
        self.validate_move_lines(banana_lines_done2, self.banana, 3, 3, package_name=package2.name, **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({
                                    'expected_location': self.picking_type_in.default_location_dest_id,
                                })
        expected_quants1  = [{'product': self.apple, 'qty': 2}, {'product': self.banana, 'qty': 2}]
        expected_quants2  = [{'product': self.apple, 'qty': 3}, {'product': self.banana, 'qty': 3}]
        self.validate_quants(package=package1, expected_quants=expected_quants1, **validation_args)
        self.validate_quants(package=package2, expected_quants=expected_quants2, **validation_args)

    def test22_target_storage_format_multiple_mixed_packages_from_two_products_pallet_products(self):
        """Tests that mutiple sets of the two products
           can be made from a single picking
           for target_storage_format pallet_products.
        """
        Package = self.env['stock.quant.package']
        package1 = Package.get_package('test_package1', create=True)
        package2 = Package.get_package('test_package2', create=True)
        validation_args = {
                            'is_pallet': True,
                          }
        create_info = [
                        {'product': self.apple, 'qty': 5},
                        {'product': self.banana, 'qty': 5},
                      ]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info1 = [
                           {'product_barcode': self.apple.barcode, 'qty': 2},
                           {'product_barcode': self.banana.barcode, 'qty': 2},
                         ]
        products_info2 = [
                           {'product_barcode': self.apple.barcode, 'qty': 3},
                           {'product_barcode': self.banana.barcode, 'qty': 3},
                         ]
        self.picking_type_in.u_target_storage_format = 'pallet_products'

        apple_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        banana_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana)
        self.validate_move_lines(apple_lines, self.apple, 5, 0)
        self.validate_move_lines(banana_lines, self.banana, 5, 0)

        picking.update_picking(products_info=products_info1, result_package_name=package1.name)
        apple_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        banana_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana and x.qty_done > 0)
        self.validate_move_lines(apple_lines_done, self.apple, 2, 2, package_name=package1.name, **validation_args)
        self.validate_move_lines(banana_lines_done, self.banana, 2, 2, package_name=package1.name, **validation_args)

        picking.update_picking(products_info=products_info2, result_package_name=package2.name)
        apple_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        banana_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana and x.qty_done > 0)
        apple_lines_done2 -= apple_lines_done
        banana_lines_done2 -= banana_lines_done
        self.validate_move_lines(apple_lines_done2, self.apple, 3, 3, package_name=package2.name, **validation_args)
        self.validate_move_lines(banana_lines_done2, self.banana, 3, 3, package_name=package2.name, **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({
                                    'expected_location': self.picking_type_in.default_location_dest_id,
                                })
        expected_quants1 = [{'product': self.apple, 'qty': 2}, {'product': self.banana, 'qty': 2}]
        expected_quants2 = [{'product': self.apple, 'qty': 3}, {'product': self.banana, 'qty': 3}]
        self.validate_quants(package=package1, expected_quants=expected_quants1, **validation_args)
        self.validate_quants(package=package2, expected_quants=expected_quants2, **validation_args)

    def test23_target_storage_format_multiple_mixed_packages_from_two_products_pallet_packages(self):
        """Tests that mutiple sets of the two products
           can be made from a single picking
           for target_storage_format pallet_packages.
        """
        Package = self.env['stock.quant.package']
        package1 = Package.get_package('test_package1', create=True)
        package2 = Package.get_package('test_package2', create=True)
        validation_args = {
                            'is_pallet': True,
                            'is_package': True
                          }
        create_info = [

                        {'product': self.apple, 'qty': 5},
                        {'product': self.banana, 'qty': 5},
                      ]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info1 = [
                           {'product_barcode': self.apple.barcode, 'qty': 2},
                           {'product_barcode': self.banana.barcode, 'qty': 2},
                         ]
        products_info2 = [
                           {'product_barcode': self.apple.barcode, 'qty': 3},
                           {'product_barcode': self.banana.barcode, 'qty': 3},
                         ]
        self.picking_type_in.u_target_storage_format = 'pallet_packages'

        apple_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        banana_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana)
        self.validate_move_lines(apple_lines, self.apple, 5, 0)
        self.validate_move_lines(banana_lines, self.banana, 5, 0)

        picking.update_picking(products_info=products_info1, result_package_name=package1.name)
        apple_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        banana_lines_done = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana and x.qty_done > 0)
        self.validate_move_lines(apple_lines_done, self.apple, 2, 2, package_name=package1.name, **validation_args)
        self.validate_move_lines(banana_lines_done, self.banana, 2, 2, package_name=package1.name, **validation_args)

        picking.update_picking(products_info=products_info2, result_package_name=package2.name)
        apple_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.qty_done > 0)
        banana_lines_done2 = picking.move_line_ids.filtered(lambda x: x.product_id == self.banana and x.qty_done > 0)
        apple_lines_done2 -= apple_lines_done
        banana_lines_done2 -= banana_lines_done
        self.validate_move_lines(apple_lines_done2, self.apple, 3, 3, package_name=package2.name, **validation_args)
        self.validate_move_lines(banana_lines_done2, self.banana, 3, 3, package_name=package2.name, **validation_args)
        picking.update_picking(validate=True)
        validation_args.update({
                                    'num_packages_expected': 1,
                                    'expected_location': self.picking_type_in.default_location_dest_id,
                                })
        expected_quants1 = [{'product': self.apple, 'qty': 2}, {'product': self.banana, 'qty': 2}]
        expected_quants2 = [{'product': self.apple, 'qty': 3}, {'product': self.banana, 'qty': 3}]
        self.validate_quants(package=package1, expected_quants=expected_quants1, **validation_args)
        self.validate_quants(package=package2, expected_quants=expected_quants2, **validation_args)

    def test24_over_receive_while_picking_type_doesnt_allow_it(self):
        """Checks that the correct error is thrown
           when over-receiving when it is not
           allowed by picking type.
        """
        self.picking_type_in.u_over_receive = False
        expected_qty = 2
        receive_qty = 6
        create_info = [{'product': self.apple, 'qty': expected_qty}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': receive_qty}]
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)

        expected_error = 'We are not expecting these extra quantities of these parts:\n' \
                         '%s: %.1f\n' \
                         'Please either receive the right amount and move the rest ' \
                         'to probres, or if they cannot be split, ' \
                         'move all to probres.' % (self.apple.name, receive_qty - expected_qty)

        self.assertEqual(e.exception.name,
                         expected_error,
                         'No/Incorrect error message was thrown')

    def test25_over_receive_while_picking_type_doesnt_allow_it(self):
        """Checks that the correct error is thrown
           when receiving an unexpected product when
           it is not allowed by picking type.
        """
        self.picking_type_in.u_over_receive = False
        expected_qty = 2
        receive_qty = 6
        create_info = [{'product': self.apple, 'qty': expected_qty}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.banana.barcode, 'qty': receive_qty}]
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)

        expected_error = 'We are not expecting these extra quantities of these parts:\n' \
                         '%s: %i\n' \
                         'Please either receive the right amount and move the rest ' \
                         'to probres, or if they cannot be split, ' \
                         'move all to probres.' % (self.banana.name, receive_qty)

        self.assertEqual(e.exception.name,
                         expected_error,
                         'No/Incorrect error message was thrown')
