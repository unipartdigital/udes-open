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
        cls.picking_type_in = user_warehouse.in_type_id
        # Setting default source location as goods_in doesn't have one
        cls.picking_type_in.default_location_src_id = cls.env.ref('stock.stock_location_suppliers')

    def test01_update_picking_validate_complete(self):
        """ Test update_picking completes in the simpliest
            case a single untracked product in a single line.
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]

        self.assertEqual(picking.move_lines.quantity_done, 0)
        picking.update_picking(products_info=products_info)
        self.assertEqual(picking.move_lines.quantity_done, 4)
        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test02_update_picking_validate_done_complete_serial_number(self):
        """ Test update_picking completes when using a tracked product
            in a single update.
        """
        create_info = [{'product': self.strawberry, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 4,
                            'serial_numbers': ['Strawberry0', 'Strawberry1',
                                               'Strawberry2', 'Strawberry3']
                        }]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0)
        picking.update_picking(products_info=products_info)
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 4)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test03_update_picking_split_lines(self):
        """ Test update_picking makes a new move_line
            when the move is incomplete and the product
            is not tracked.
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': 2}]

        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0.0)
        picking.update_picking(products_info=products_info)

        move_lines = picking.move_line_ids
        self.assertEqual(sorted(move_lines.mapped('qty_done')), sorted([2.0, 0.0]),
                         'After processing 2/4 apples there ' \
                         'should be two movelines with qty_done ' \
                         'of 0 and 2')

        picking.update_picking(products_info=products_info)
        self.assertEqual(move_lines.mapped('qty_done'), [2.0, 2.0],
                         'After processing (2 moves of 2)/4 ' \
                         'apples there should be two movelines ' \
                         'with qty_done 2 in both')

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test04_update_picking_split_lines_with_serial_number(self):
        """ Checking that two calls of update_picking each with two
            serial numbers produces the expected changes in the
            move_lines
        """
        create_info = [{'product': self.strawberry, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info_1 = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 2,
                            'serial_numbers': ['Strawberry0', 'Strawberry1']
                        }]
        products_info_2 = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 2,
                            'serial_numbers': ['Strawberry2', 'Strawberry3']
                        }]

        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0.0)

        picking.update_picking(products_info=products_info_1)
        self.assertEqual(len(picking.move_line_ids.filtered(lambda x: x.qty_done == 1.0)),
                         2,
                         'Two of the 4 expected should be done here')

        picking.update_picking(products_info=products_info_2)
        self.assertEqual(len(picking.move_line_ids.filtered(lambda x: x.qty_done == 1.0)),
                         4,
                         'All move lines should be done here')

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test05_update_picking_incomplete_validate_fail_then_backorder(self):
        """ Checks that validation fails if the move_lines are incomplete
            then checks that validation is allowed when create_backorder is True
            it also verifies the backorder is created as expected.
        """
        Picking = self.env['stock.picking']
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': 3}]
        picking.update_picking(products_info=products_info)

        with self.assertRaises(ValidationError) as e:
            picking.update_picking(validate=True)
        self.assertEqual(e.exception.name,
                         'Cannot validate transfer because there ' \
                         'are move lines todo',
                         'No/Incorrect error message was thrown')

        picking.update_picking(validate=True, create_backorder=True)
        backorder = Picking.get_pickings(backorder_id=picking.id)
        self.assertEqual(len(backorder), 1, 'No (or more than 1) backorder was created')
        expected_move_lines = backorder.move_line_ids.filtered(lambda x: x.product_id == self.apple \
                                                               and x.ordered_qty == 1)
        self.assertEqual(len(expected_move_lines), 1)

    def test06_update_picking_unequal_serial_number_length(self):
        """ Checks that the correct validation error is thrown
            when the number of serial numbers does not match the
            quantiy provided.
        """
        create_info = [{'product': self.strawberry, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 4,
                            'serial_numbers': ['Strawberry0','Strawberry1', 'Strawberry2']
                        }]
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)
        self.assertEqual(e.exception.name, 'The number of serial numbers and quantity done does not ' \
                                           'match for product Test product Strawberry',
                         'No/Incorrect error message was thrown')

    def test07_update_picking_repeated_serial_number(self):
        """ Checks that the correct error is thrown when
                a serial number is repeated in a single call
            to update_picking.
        """
        create_info = [{'product': self.strawberry, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        sn0 = ['Strawberry0']
        products_info = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 1,
                            'serial_numbers': sn0
                        },
                        {
                            'product_barcode': self.strawberry.barcode,
                            'qty': 1,
                            'serial_numbers': sn0
                        }]

        einfo = (' '.join(sn0), picking.name, self.strawberry.name)
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)
        self.assertEqual(e.exception.name, 'Serial numbers %s are repeated '
                                           'in picking %s for product %s' % einfo,
                         'No/Incorrect error message was thrown')

    def test08_update_picking_repeated_serial_number_individual_calls(self):
        """ Checks that the correct error is thrown when
            when a serial number is repeated in a seperate call
            to update_picking.
        """
        create_info = [{'product': self.strawberry, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 1,
                            'serial_numbers': ['Strawberry0']
                        }]
        picking.update_picking(products_info=products_info)

        with self.assertRaises(ValidationError) as e:
            picking.update_picking(products_info=products_info)
        self.assertEqual(e.exception.name, 'Serial numbers Strawberry0 already exist '
                                             'in picking %s' % picking.name,
                         'No/Incorrect error message was thrown')

    def test09_update_picking_over_received_single(self):
        """ Testing if over receiving products in a single
            call behaves as expected.
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        products_info = [{'product_barcode': self.apple.barcode, 'qty': 5}]

        self.assertEqual(picking.move_line_ids.qty_done, 0.0)
        picking.update_picking(products_info=products_info)
        # check ordered_qty and qty_done  are as expected
        self.assertEqual(picking.move_line_ids.ordered_qty, 4)
        self.assertEqual(picking.move_lines.ordered_qty, 4)
        self.assertEqual(picking.move_line_ids.qty_done, 5)
        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test10_update_picking_over_received_split_lines(self):
        """ testing that over receiving products in seperate
            calls behave as expected creates a second move_line
            and its orded_qty is zero.
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      origin='self_picking_origin',
                                      products_info=create_info,
                                      confirm=True)
        products_info1 = [{'product_barcode': self.apple.barcode, 'qty': 4}]
        products_info2 = [{'product_barcode': self.apple.barcode, 'qty': 2}]

        self.assertEqual(picking.move_line_ids.qty_done, 0.0)
        picking.update_picking(products_info=products_info1)
        expected_move_lines = picking.move_line_ids.filtered(lambda x: x.ordered_qty == 4)
        self.assertEqual(expected_move_lines.qty_done, 4.0)

        picking.update_picking(products_info=products_info2)
        unexpected_move_lines = picking.move_line_ids.filtered(lambda x: x.ordered_qty == 0)
        self.assertEqual(unexpected_move_lines.qty_done, 2.0)
        self.assertEqual(picking.move_lines.ordered_qty, 4)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test11_update_picking_only_unexpected_product(self):
        """ Checks that an unexpected product is put into
            a newly created move_line.
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [{'product_barcode': self.cherry.barcode, 'qty': 2}]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0.0)
        picking.update_picking(products_info=products_info)
        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.cherry and x.ordered_qty ==0)
        self.assertEqual(cherry_move_lines.qty_done, 2)
        cherry_moves = cherry_move_lines.mapped('move_id')
        self.assertEqual(cherry_moves.ordered_qty, 0)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.ordered_qty ==4)
        self.assertEqual(apple_move_lines.qty_done, 0)

    def test12_update_picking_unexpected_and_expected_product(self):
        """ Checks that the picking of an expected and unexpected
            product in a single call produces the desired result.
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        products_info = [
                            {'product_barcode': self.cherry.barcode, 'qty': 4},
                            {'product_barcode': self.apple.barcode, 'qty': 4},
                        ]

        self.assertEqual(sum(picking.move_line_ids.mapped('qty_done')), 0.0)
        picking.update_picking(products_info=products_info)

        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.cherry and x.ordered_qty == 0)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        cherry_moves = cherry_move_lines.mapped('move_id')
        self.assertEqual(cherry_moves.ordered_qty, 0)

        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.ordered_qty == 4)
        self.assertEqual(apple_move_lines.qty_done, 4)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test13_update_picking_two_products(self):
        """ Checks that the picking of two products
            in a single call behaves as expected.
        """
        creation_info = [
                            {'product': self.apple, 'qty': 4},
                            {'product': self.cherry, 'qty': 4},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=creation_info,
                                      confirm=True)

        products_info = [
                            {'product_barcode': self.cherry.barcode, 'qty': 4},
                            {'product_barcode': self.apple.barcode, 'qty': 4},
                        ]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0.0)
        picking.update_picking(products_info=products_info)
        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.cherry and x.ordered_qty == 4)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.ordered_qty == 4)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.qty_done, 4)

    def test14_update_picking_two_products_single_product_per_update(self):
        """ Checks that receiving two products using two
            calls of update_picking produces the expected
            results.
        """
        creation_info = [
                            {'product': self.apple, 'qty': 4},
                            {'product': self.cherry, 'qty': 4},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=creation_info,
                                      confirm=True)

        cherry_info = [{'product_barcode': self.cherry.barcode, 'qty': 4}]
        apple_info = [{'product_barcode': self.apple.barcode, 'qty': 4}]

        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.cherry and x.ordered_qty ==4)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.ordered_qty ==4)

        self.assertEqual(sum(picking.move_line_ids.mapped('qty_done')), 0.0)

        picking.update_picking(products_info=cherry_info)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.qty_done, 0)

        picking.update_picking(products_info=apple_info)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.qty_done, 4)

    def test15_update_picking_two_products_one_with_serial_numbers(self):
        """ Checks update_picking with two expected products when
            one product is tracked using serial numbers.
        """

        creation_info = [
                            {'product': self.apple, 'qty': 2},
                            {'product': self.strawberry, 'qty': 2},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                     origin='test_picking_origin',
                                     products_info=creation_info,
                                     confirm=True)

        strawberry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.strawberry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(len(strawberry_move_lines), 2)
        self.assertEqual(len(apple_move_lines), 1)
        products_info = [
                            {
                                'product_barcode': self.apple.barcode,
                                'qty':2
                            },
                            {
                                'product_barcode': self.strawberry.barcode,
                                'qty': 2,
                                'serial_numbers': ['Strawberry0', 'Strawberry1'],
                            },
                        ]
        picking.update_picking(products_info=products_info)

        strawberry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.strawberry)
        self.assertEqual(sum(strawberry_move_lines.mapped('qty_done')), 2)

        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(apple_move_lines.qty_done, 2)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Stock picking is not in state done after validation.')

    def test16_update_picking_set_result_package_id(self):
        """ Checks the correct result_package_id is set when
            result_package_name is used in update_picking.
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
        packaged_move_lines = picking.mapped('move_line_ids').filtered(lambda x: x.result_package_id == package)
        self.assertEqual(len(packaged_move_lines), 1)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Stock picking is not in state done after validation.')

    def test17_update_picking_set_result_package_id_mixed_package(self):
        """ Checks the correct result_package_id is set by update_picking
            when using result_package_name with two products.
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        creation_info = [
                            {'product': self.apple, 'qty': 2},
                            {'product': self.cherry, 'qty': 2},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                     origin='test_picking_origin',
                                     products_info=creation_info,
                                     confirm=True)
        products_info = [
                            {'product_barcode': self.apple.barcode, 'qty': 2},
                            {'product_barcode': self.cherry.barcode, 'qty': 2},
                        ]

        picking.update_picking(products_info=products_info, result_package_name=package.name)
        packaged_move_lines = picking.mapped('move_line_ids').filtered(lambda x: x.result_package_id == package)
        self.assertEqual(len(packaged_move_lines), 2)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test18_update_picking_set_result_package_id_serial_numbers_one_per_update(self):
        """ Checks the correct result_package_id is set by update_picking
            when using result_package_name over two calls when the
            product is tracked.
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        creation_info = [{'product': self.strawberry, 'qty': 2}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=creation_info,
                                      confirm=True)
        products_info_1 = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 1,
                            'serial_numbers': ['Strawberry0']
                        }]

        products_info_2 = [{
                            'product_barcode': self.strawberry.barcode,
                            'qty': 1,
                            'serial_numbers': ['Strawberry1']
                        }]

        picking.update_picking(products_info=products_info_1, result_package_name=package.name)
        picking.update_picking(products_info=products_info_2, result_package_name=package.name)
        packaged_move_lines = picking.mapped('move_line_ids').filtered(lambda x: x.result_package_id == package)
        self.assertEqual(len(packaged_move_lines), 2)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test19_update_picking_set_result_package_id_mixed_package_one_with_serial_numbers(self):
        """ Checks the correct result_package_id is set by update_picking
            when using result_package_name for two products when one is tracked.
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        creation_info = [
                            {'product': self.apple, 'qty': 2},
                            {'product': self.strawberry, 'qty': 2},
                        ]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=creation_info,
                                      confirm=True)
        products_info = [
                            {
                                'product_barcode': self.apple.barcode,
                                'qty': 2,
                            },
                            {
                                'product_barcode': self.strawberry.barcode,
                                'qty': 2,
                                'serial_numbers': ['Strawberry0', 'Strawberry1'],
                            },
                        ]
        picking.update_picking(products_info=products_info, result_package_name=package.name)
        packaged_move_lines = picking.mapped('move_line_ids').filtered(lambda x: x.result_package_id == package)
        self.assertEqual(len(packaged_move_lines), 3)
        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')
