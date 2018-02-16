from . import common
from odoo.exceptions import ValidationError

class TestGoodsInUpdatePicking(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInUpdatePicking, cls).setUpClass()
        # Pretty much TestGoodsInPicking Setup
        User = cls.env['res.users']
        PickingType = cls.env['stock.picking.type']
        Picking = cls.env['stock.picking']
        user_warehouse = User.get_user_warehouse()
        # Get goods in type
        in_type_id = user_warehouse.in_type_id
        cls.picking_type_in = PickingType.search([('id', '=', in_type_id.id)])
        # Setting default source location as goods_in doesn't have one
        cls.picking_type_in.default_location_src_id = cls.env.ref('stock.stock_location_suppliers')

    def test01_update_picking_validate_complete(self):
        """ Test update_picking by addding by splitting a product
            without serial numbers
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        picking.update_picking(products_info=products_info)
        self.assertEqual(picking.move_lines.quantity_done, 4)
        picking.update_picking(validate=True)
        self.assertEqual(picking.move_lines.state, 'done')

    def test02_update_picking_validate_done_complete_serial_number(self):
        """ Test update_picking by addding by splitting a product
            without serial numbers
        """
        self.apple.write({'tracking': 'serial'})
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.apple.barcode,
                            'qty': 4,
                            'serial_numbers': ['Apple0', 'Apple1',
                                               'Apple2','Apple3']
                        }]
        picking.update_picking(products_info=products_info)
        self.assertEqual(picking.move_lines.quantity_done, 4)
        picking.update_picking(validate=True)
        self.assertEqual(picking.move_lines.state, 'done')

    def test03_update_picking_split_lanes(self):
        """ Test update_picking makes new move_lines
            when called a second time
        """
        # Without deep copy this will need remaking!
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': 2}]
        picking.update_picking(products_info=products_info)
        moves_lines = picking.move_line_ids
        self.assertEqual(sorted(moves_lines.mapped('qty_done')), sorted([0.0, 2.0]), 'After processing 5/10 apples there ' \
                                                                                     'should be two movelines with qty_done ' \
                                                                                     'of 0 and 5')

        picking.update_picking(products_info=products_info)
        moves_lines = picking.move_line_ids
        self.assertEqual(sorted(moves_lines.mapped('qty_done')), sorted([2.0, 2.0]),
                         'After processing (2 moves of 5)/10 ' \
                         'apples there should be two movelines ' \
                         'with qty_done 5 in both')

        picking.update_picking(validate=True)
        self.assertEqual(picking.move_lines.state, 'done', 'Process doesn\'t complete')

    def test04_update_picking_split_lanes_with_serial_number(self):
        """ Checking that two of updates the picking with two serial
            numbers in each produces the expected changes in the
            move_lines
        """
        self.apple.write({'tracking': 'serial'})
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.apple.barcode,
                            'qty': 2,
                            'serial_numbers': ['Apple0', 'Apple1']
                        }]
        picking.update_picking(products_info=products_info)
        moves_lines = picking.move_line_ids
        # Note 4 move lines are expected as when tracking = serial odoo makes move lines for each qty
        self.assertEqual(moves_lines.mapped('qty_done'),
                         [1.0, 1.0, 0.0, 0.0],
                         'Two of the 4 expected should be done here')

        products_info[0]['serial_numbers'] = ['Apple2', 'Apple3']
        picking.update_picking(products_info=products_info)
        moves_lines = picking.move_line_ids
        self.assertEqual(moves_lines.mapped('qty_done'),
                         [1.0, 1.0, 1.0, 1.0],
                         'All move lines should be done here')

        picking.update_picking(validate=True)
        self.assertEqual(picking.move_lines.state, 'done', 'Process doesn\'t complete')

    def test05_update_picking_incomplete_validate_fail_then_backorder(self):
        """ Checks that validation fails on if the move_lines are incomplete
            then checks that validation is allowed when
            setting create_backorder and that backorder is created
        """
        Picking = self.env['stock.picking']
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': 3}]
        picking.update_picking(products_info=products_info)
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(validate=True)
        self.assertEqual(e.exception.name, 'Cannot validate transfer because there are move lines todo',
                         'No/Incorrect error message was thrown')

        picking.update_picking(validate=True, create_backorder=True)
        backorder = Picking.get_pickings(backorder_id=picking.id)
        self.assertEqual(len(backorder), 1, 'No (or more than 1) backorder was created')

    def test06_update_picking_unequal_serial_number_length(self):
        """ Checks that the correct validation error is thrown
            when the number of serial numbers does not match the quantiy
            provided.
        """
        self.apple.write({'tracking': 'serial'})
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.apple.barcode,
                            'qty': 4,
                            'serial_numbers': ['Apple0','Apple1', 'Apple2']
                        }]
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)
        self.assertEqual(e.exception.name, 'The number of serial numbers and quantity done does not ' \
                                           'match for product Test product Apple',
                         'No/Incorrect error message was thrown')

    def test07_update_picking_repeated_serial_number(self):
        """ Checks that the correct error is thrown when
            when a serial number is repeated.
        """
        self.apple.write({'tracking': 'serial'})
        create_info = [{'product': self.apple, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.apple.barcode,
                            'qty': 1,
                            'serial_numbers': ['Apple0']
                        },
                        {
                            'product_barcode': self.apple.barcode,
                            'qty': 1,
                            'serial_numbers': ['Apple0']
                        }]
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)
            self.assertEqual(e.exception.name, 'The serial number Apple0 is repeated in picking '
                                               '%s for product Test product Apple' % picking.name,
                             'No/Incorrect error message was thrown')

    def test08_update_picking_repeated_serial_number_split(self):
        """ Checks that the correct error is thrown when
            when a serial number is repeated in a second call
            to update_picking.
        """
        self.apple.write({'tracking': 'serial'})
        create_info = [{'product': self.apple, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.apple.barcode,
                            'qty': 1,
                            'serial_numbers': ['Apple0']
                        }]
        picking.update_picking(products_info=products_info)

        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)
        self.assertEqual(e.exception.name, 'Serial numbers Apple0 already exist '
                                             'in picking %s' % picking.name,
                         'No/Incorrect error message was thrown')

    def test09_update_picking_over_recived_single(self):
        """ testing if over recived products in a single
            call behaves as expected
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': 5}]
        picking.update_picking(products_info=products_info)
        # check ordered_qty and qty_done  are as expected
        self.assertEqual(picking.move_line_ids.ordered_qty, 4)
        self.assertEqual(picking.move_line_ids.qty_done, 5)
        picking.update_picking(validate=True)
        self.assertEqual(picking.move_lines.state, 'done', 'Process doesn\'t complete')

    def test10_update_picking_over_recived_split_lines(self):
        """ testing if over recived products in seperate
            calls behave as expected
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='self_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        picking.update_picking(products_info=products_info)
        products_info[0]['qty'] =  2
        picking.update_picking(products_info=products_info)
        # Note this isn't sorted to check the order of the split
        self.assertEqual(picking.mapped('move_line_ids.ordered_qty'), [4.0, 0.0])
        self.assertEqual(picking.mapped('move_line_ids.qty_done'), [4.0, 2.0])
        self.assertEqual(picking.move_lines.ordered_qty, 4.0, 'Only 4 was expected')
        self.assertEqual(picking.move_lines.quantity_done, 6.0,
                         'The quantity done should be the total of 6')

    def test11_update_picking_only_unexpected_product(self):
        """ Checks that an unexpected product is put into
            it's own newly created move_line.
        """
        cherry = self.create_product('Cherry')
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{'product_barcode': cherry.barcode, 'qty': 2}]
        picking.update_picking(products_info=products_info)
        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == cherry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(cherry_move_lines.ordered_qty, 0)
        self.assertEqual(cherry_move_lines.qty_done, 2)
        self.assertEqual(apple_move_lines.ordered_qty, 4)
        self.assertEqual(apple_move_lines.qty_done, 0)


    def test12_update_picking_unexpected_and_expected_product(self):
        """ Checks that the picking of an expected and unexpected
            product together produces the desired result.
        """
        cherry = self.create_product('Cherry')
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info = [
                            {'product_barcode': cherry.barcode, 'qty': 4},
                            {'product_barcode': self.apple.barcode, 'qty': 4},
                        ]
        picking.update_picking(products_info=products_info)
        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == cherry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(cherry_move_lines.ordered_qty, 0)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.ordered_qty, 4)
        self.assertEqual(apple_move_lines.qty_done, 4)

    def test13_update_picking_two_products(self):
        """ Checks that the picking of two products behaves
            in a single call as expected.
        """
        cherry = self.create_product('Cherry')
        creation_info = [
                            {'product': self.apple, 'qty': 4},
                            {'product': cherry, 'qty': 4},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=creation_info,
                                      confirm=True)

        products_info = [
                            {'product_barcode': cherry.barcode, 'qty': 4},
                            {'product_barcode': self.apple.barcode, 'qty': 4},
                        ]
        picking.update_picking(products_info=products_info)
        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == cherry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(cherry_move_lines.ordered_qty, 4)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.ordered_qty, 4)
        self.assertEqual(apple_move_lines.qty_done, 4)

    def test14_update_picking_two_products_split_lines(self):
        """ checks that reciving two products using two
            calls of update_picking produces the expected
            results
        """
        cherry = self.create_product('Cherry')
        creation_info = [
                            {'product': self.apple, 'qty': 4},
                            {'product': cherry, 'qty': 4},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=creation_info,
                                      confirm=True)

        cherry_info = [{'product_barcode': cherry.barcode, 'qty': 4}]
        picking.update_picking(products_info=cherry_info)
        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == cherry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(cherry_move_lines.ordered_qty, 4)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.ordered_qty, 4)
        self.assertEqual(apple_move_lines.qty_done, 0)

        apple_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        picking.update_picking(products_info=apple_info)
        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == cherry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(cherry_move_lines.ordered_qty, 4)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.ordered_qty, 4)
        self.assertEqual(apple_move_lines.qty_done, 4)

    def test15_update_picking_two_products_one_with_serial_numbers(self):
        """ checks update_picking with two expected products when
            one product is tracked using serial numbers.
        """

        cherry = self.create_product('Cherry')
        cherry.tracking = 'serial'
        creation_info = [
                            {'product': self.apple, 'qty': 2},
                            {'product': cherry, 'qty': 2},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                     origin='test_picking_origin',
                                     products_info=creation_info,
                                     confirm=True)

        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == cherry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(len(cherry_move_lines), 2)
        self.assertEqual(len(apple_move_lines), 1)
        products_info = [
                            {
                                'product_barcode': self.apple.barcode,
                                'qty':2
                            },
                            {
                                'product_barcode': cherry.barcode,
                                'qty': 2,
                                'serial_numbers': ['Cherry0', 'Cherry1'],
                            },
                        ]
        picking.update_picking(products_info=products_info)
        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == cherry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(sum(cherry_move_lines.mapped('qty_done')), 2)
        self.assertEqual(apple_move_lines.qty_done, 2)
        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Process doesn\'t complete')

    def test16_update_picking_set_result_package_id(self):
        """ checks the correct result_package_id is set when
            result_package_name is used in update_picking
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        creation_info = [{'product': self.apple, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                     origin='test_picking_origin',
                                     products_info=creation_info,
                                     confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty':2}]
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.assertEqual(picking.move_line_ids.result_package_id, package)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Process doesn\'t complete')

    def test17_update_picking_set_result_package_id_mixed_package(self):
        """ checks the correct result_package_id is set when
            result_package_name is used in update_picking when the
            there is two products
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        cherry = self.create_product('Cherry')
        creation_info = [
                            {'product': self.apple, 'qty': 2},
                            {'product': cherry, 'qty': 2},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                     origin='test_picking_origin',
                                     products_info=creation_info,
                                     confirm=True)
        products_info = [
                            {
                                'product_barcode': self.apple.barcode,
                                'qty':2
                            },
                            {
                                'product_barcode': cherry.barcode,
                                'qty': 2,
                            },
                        ]
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.assertEqual(picking.mapped('move_line_ids.result_package_id'), package)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Process doesn\'t complete')

    def test18_update_picking_set_result_package_id_serial_numbers_split(self):
        """ checks the correct result_package_id is set when
            result_package_name is used in update_picking when the
            product has a serial_number over two calls
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        self.apple.tracking = 'serial'
        creation_info = [{'product': self.apple, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=creation_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.apple.barcode,
                            'qty': 1,
                            'serial_numbers': ['Apple0']
                        }]
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        products_info[0]['serial_numbers'] = ['Apple1']
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.assertEqual(picking.mapped('move_line_ids.result_package_id'), package)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Process doesn\'t complete')

    def test19_update_picking_set_result_package_id_mixed_package_one_with_serial_numbers(self):
        """ checks the correct result_package_id is set when
            result_package_name is used in update_picking when
            there is two products and one has serial_numbers
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        cherry = self.create_product('Cherry')
        cherry.tracking = 'serial'
        creation_info = [
                            {'product': self.apple, 'qty': 2},
                            {'product': cherry, 'qty': 2},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                      origin='test_picking_origin',
                                      products_info=creation_info,
                                      confirm=True)
        products_info = [
                            {
                                'product_barcode': self.apple.barcode,
                                'qty':2
                            },
                            {
                                'product_barcode': cherry.barcode,
                                'qty': 2,
                                'serial_numbers': ['Cherry0', 'Cherry1'],
                            },
                        ]
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        self.assertEqual(picking.mapped('move_line_ids.result_package_id'), package)
        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Process doesn\'t complete')
