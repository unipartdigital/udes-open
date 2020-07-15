from . import common
from odoo.exceptions import ValidationError


class TestGoodsInUpdatePickingProducts(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInUpdatePickingProducts, cls).setUpClass()
        cls.picking_type_in.u_target_storage_format = 'product'

    def test01_update_picking_validate_complete(self):
        """ Test update_picking completes in the simpliest
            case a single untracked product in a single line.
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.apple.barcode, 'qty': 4}]

        self.assertEqual(picking.move_lines.quantity_done, 0)
        picking.update_picking(product_ids=product_ids)
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
        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.strawberry.barcode,
                        'qty': 4,
                        'lot_names': ['Strawberry0', 'Strawberry1',
                                      'Strawberry2', 'Strawberry3']
                        }]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0)
        picking.update_picking(product_ids=product_ids)
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

        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.apple.barcode, 'qty': 2}]

        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0.0)
        picking.update_picking(product_ids=product_ids)

        move_lines = picking.move_line_ids
        self.assertEqual(sorted(move_lines.mapped('qty_done')), sorted([2.0, 0.0]),
                         'After processing 2/4 apples there ' \
                         'should be two movelines with qty_done ' \
                         'of 0 and 2')

        picking.update_picking(product_ids=product_ids)
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
        picking = picking.sudo(self.inbound_user)

        product_ids_1 = [{
                            'barcode': self.strawberry.barcode,
                            'qty': 2,
                            'lot_names': ['Strawberry0', 'Strawberry1']
                        }]
        product_ids_2 = [{
                            'barcode': self.strawberry.barcode,
                            'qty': 2,
                            'lot_names': ['Strawberry2', 'Strawberry3']
                        }]

        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0.0)

        picking.update_picking(product_ids=product_ids_1)
        self.assertEqual(len(picking.move_line_ids.filtered(lambda x: x.qty_done == 1.0)),
                         2,
                         'Two of the 4 expected should be done here')

        picking.update_picking(product_ids=product_ids_2)
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

        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.apple.barcode, 'qty': 3}]
        picking.update_picking(product_ids=product_ids)

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
        picking = picking.sudo(self.inbound_user)

        product_ids = [{
                            'barcode': self.strawberry.barcode,
                            'qty': 4,
                            'lot_names': ['Strawberry0','Strawberry1', 'Strawberry2']
                        }]
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(product_ids=product_ids)
        self.assertEqual(e.exception.name,
                         'The number of serial numbers and quantity done does '
                         'not match for product Test product Strawberry',
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
        picking = picking.sudo(self.inbound_user)

        sn0 = ['Strawberry0']
        product_ids = [{
                            'barcode': self.strawberry.barcode,
                            'qty': 1,
                            'lot_names': sn0
                        },
                        {
                            'barcode': self.strawberry.barcode,
                            'qty': 1,
                            'lot_names': sn0
                        }]

        einfo = (' '.join(sn0), picking.name, self.strawberry.name)
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(product_ids=product_ids)
        self.assertEqual(e.exception.name, 'Lot numbers %s are repeated '
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
        picking = picking.sudo(self.inbound_user)

        product_ids = [{
            'barcode': self.strawberry.barcode,
            'qty': 1,
            'lot_names': ['Strawberry0']
        }]
        picking.update_picking(product_ids=product_ids)

        with self.assertRaises(ValidationError) as e:
            picking.update_picking(product_ids=product_ids)
        self.assertEqual(e.exception.name,
                         'Serial numbers Strawberry0 already exist in '
                         'picking %s' % picking.name,
                         'No/Incorrect error message was thrown')

    def test09_update_picking_over_received_single(self):
        """ Testing if over receiving products in a single
            call behaves as expected.
        """
        create_info = [{'product': self.apple, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)

        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.apple.barcode, 'qty': 5}]

        self.assertEqual(picking.move_line_ids.qty_done, 0.0)
        picking.update_picking(product_ids=product_ids)
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
        picking = picking.sudo(self.inbound_user)

        product_ids1 = [{'barcode': self.apple.barcode, 'qty': 4}]
        product_ids2 = [{'barcode': self.apple.barcode, 'qty': 2}]

        self.assertEqual(picking.move_line_ids.qty_done, 0.0)
        picking.update_picking(product_ids=product_ids1)
        expected_move_lines = picking.move_line_ids.filtered(lambda x: x.ordered_qty == 4)
        self.assertEqual(expected_move_lines.qty_done, 4.0)

        picking.update_picking(product_ids=product_ids2)
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
        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.cherry.barcode, 'qty': 2}]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0.0)
        picking.update_picking(product_ids=product_ids)
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
        picking = picking.sudo(self.inbound_user)

        product_ids = [
                            {'barcode': self.cherry.barcode, 'qty': 4},
                            {'barcode': self.apple.barcode, 'qty': 4},
                        ]

        self.assertEqual(sum(picking.move_line_ids.mapped('qty_done')), 0.0)
        picking.update_picking(product_ids=product_ids)

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
        picking = picking.sudo(self.inbound_user)

        product_ids = [
                            {'barcode': self.cherry.barcode, 'qty': 4},
                            {'barcode': self.apple.barcode, 'qty': 4},
                        ]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0.0)
        picking.update_picking(product_ids=product_ids)
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
        picking = picking.sudo(self.inbound_user)

        cherry_info = [{'barcode': self.cherry.barcode, 'qty': 4}]
        apple_info = [{'barcode': self.apple.barcode, 'qty': 4}]

        cherry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.cherry and x.ordered_qty ==4)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple and x.ordered_qty ==4)

        self.assertEqual(sum(picking.move_line_ids.mapped('qty_done')), 0.0)

        picking.update_picking(product_ids=cherry_info)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.qty_done, 0)

        picking.update_picking(product_ids=apple_info)
        self.assertEqual(cherry_move_lines.qty_done, 4)
        self.assertEqual(apple_move_lines.qty_done, 4)

    def test15_update_picking_two_products_one_with_lot_names(self):
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
        picking = picking.sudo(self.inbound_user)

        strawberry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.strawberry)
        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(len(strawberry_move_lines), 2)
        self.assertEqual(len(apple_move_lines), 1)
        product_ids = [
                            {
                                'barcode': self.apple.barcode,
                                'qty':2
                            },
                            {
                                'barcode': self.strawberry.barcode,
                                'qty': 2,
                                'lot_names': ['Strawberry0', 'Strawberry1'],
                            },
                        ]
        picking.update_picking(product_ids=product_ids)

        strawberry_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.strawberry)
        self.assertEqual(sum(strawberry_move_lines.mapped('qty_done')), 2)

        apple_move_lines = picking.move_line_ids.filtered(lambda x: x.product_id == self.apple)
        self.assertEqual(apple_move_lines.qty_done, 2)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Stock picking is not in state done after validation.')

    def test16_update_picking_validate_done_complete_lot_number(self):
        """ Test update_picking completes when using a lot tracked product
            in a single update.
        """
        create_info = [{'product': self.tangerine, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.tangerine.barcode,
                        'qty': 4,
                        'lot_names': ['tangerine01']
                        }]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0)
        picking.update_picking(product_ids=product_ids)
        self.assertEqual(len(picking.move_line_ids), 1)
        self.assertEqual(picking.move_line_ids.qty_done, 4)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test17_update_picking_validate_done_complete_two_lot_numbers(self):
        """ Test update_picking completes when using a lot tracked product
            in two updates.
        """
        create_info = [{'product': self.tangerine, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)

        product_ids1 = [{'barcode': self.tangerine.barcode,
                        'qty': 1,
                        'lot_names': ['tangerine01']
                        }]
        product_ids2 = [{'barcode': self.tangerine.barcode,
                        'qty': 3,
                        'lot_names': ['tangerine02']
                        }]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0)
        picking.update_picking(product_ids=product_ids1)
        self.assertEqual(len(picking.move_line_ids), 2)
        first_ml = picking.move_line_ids.filtered(lambda ml: ml.qty_done > 0)
        remaining_ml = picking.move_line_ids - first_ml
        self.assertEqual(first_ml.qty_done, 1)
        self.assertEqual(first_ml.lot_name, 'tangerine01')
        self.assertFalse(remaining_ml.lot_name)

        picking.update_picking(product_ids=product_ids2)
        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(remaining_ml.qty_done, 3)
        self.assertEqual(remaining_ml.lot_name, 'tangerine02')

        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 4)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test18_update_picking_repeated_lot_number(self):
        """ Test update_picking completes when using a lot tracked product
            in two updates and using the same lot number twice.
        """
        create_info = [{'product': self.tangerine, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)

        product_ids1 = [{'barcode': self.tangerine.barcode,
                        'qty': 1,
                        'lot_names': ['tangerine01']
                        }]
        product_ids2 = [{'barcode': self.tangerine.barcode,
                        'qty': 3,
                        'lot_names': ['tangerine01']
                        }]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0)
        picking.update_picking(product_ids=product_ids1)
        self.assertEqual(len(picking.move_line_ids), 2)
        first_ml = picking.move_line_ids.filtered(lambda ml: ml.qty_done > 0)
        remaining_ml = picking.move_line_ids - first_ml
        self.assertEqual(first_ml.qty_done, 1)
        self.assertEqual(first_ml.lot_name, 'tangerine01')
        self.assertFalse(remaining_ml.lot_name)

        picking.update_picking(product_ids=product_ids2)
        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(remaining_ml.qty_done, 3)
        self.assertEqual(remaining_ml.lot_name, 'tangerine01')

        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 4)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')


class TestGoodsInUpdatePickingPallet(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInUpdatePickingPallet, cls).setUpClass()
        cls.picking_type_in.u_target_storage_format = 'pallet_products'

    def test01_update_picking_set_result_package_id(self):
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
        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.apple.barcode, 'qty':2}]
        picking.update_picking(product_ids=product_ids, result_package_name=package.name)
        packaged_move_lines = picking.mapped('move_line_ids').filtered(lambda x: x.result_package_id == package)
        self.assertEqual(len(packaged_move_lines), 1)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done', 'Stock picking is not in state done after validation.')

    def test02_update_picking_set_result_package_id_mixed_package(self):
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
        picking = picking.sudo(self.inbound_user)

        product_ids = [
                            {'barcode': self.apple.barcode, 'qty': 2},
                            {'barcode': self.cherry.barcode, 'qty': 2},
                        ]

        picking.update_picking(product_ids=product_ids, result_package_name=package.name)
        packaged_move_lines = picking.mapped('move_line_ids').filtered(lambda x: x.result_package_id == package)
        self.assertEqual(len(packaged_move_lines), 2)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test03_update_picking_set_result_package_id_lot_names_one_per_update(self):
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
        picking = picking.sudo(self.inbound_user)

        product_ids_1 = [{
                            'barcode': self.strawberry.barcode,
                            'qty': 1,
                            'lot_names': ['Strawberry0']
                        }]

        product_ids_2 = [{
                            'barcode': self.strawberry.barcode,
                            'qty': 1,
                            'lot_names': ['Strawberry1']
                        }]

        picking.update_picking(product_ids=product_ids_1, result_package_name=package.name)
        picking.update_picking(product_ids=product_ids_2, result_package_name=package.name)
        packaged_move_lines = picking.mapped('move_line_ids').filtered(lambda x: x.result_package_id == package)
        self.assertEqual(len(packaged_move_lines), 2)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test04_update_picking_set_result_package_id_mixed_package_one_with_lot_names(self):
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
        picking = picking.sudo(self.inbound_user)

        product_ids = [
                            {
                                'barcode': self.apple.barcode,
                                'qty': 2,
                            },
                            {
                                'barcode': self.strawberry.barcode,
                                'qty': 2,
                                'lot_names': ['Strawberry0', 'Strawberry1'],
                            },
                        ]
        picking.update_picking(product_ids=product_ids, result_package_name=package.name)
        packaged_move_lines = picking.mapped('move_line_ids').filtered(lambda x: x.result_package_id == package)
        self.assertEqual(len(packaged_move_lines), 3)
        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test05_update_picking_set_result_package_id_one_lot_number(self):
        """ Test update_picking completes when using a lot tracked product
            in a single update also setting result package_id.
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        create_info = [{'product': self.tangerine, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)

        product_ids = [{'barcode': self.tangerine.barcode,
                        'qty': 4,
                        'lot_names': ['tangerine01']
                        }]
        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0)
        picking.update_picking(product_ids=product_ids,
                               result_package_name=package.name)
        self.assertEqual(len(picking.move_line_ids), 1)
        self.assertEqual(picking.move_line_ids.qty_done, 4)

        packaged_move_lines = picking.mapped('move_line_ids').filtered(
            lambda x: x.result_package_id == package and x.lot_name == 'tangerine01')
        self.assertEqual(len(packaged_move_lines), 1)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test06_update_picking_set_result_package_id_two_lot_numbers(self):
        """ Test update_picking completes when using a lot tracked product
            in two updates also setting result package_id.
        """
        Package = self.env['stock.quant.package']
        package = Package.get_package('test_package', create=True)

        create_info = [{'product': self.tangerine, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)

        product_ids1 = [{'barcode': self.tangerine.barcode,
                        'qty': 1,
                        'lot_names': ['tangerine01']
                        }]
        product_ids2 = [{'barcode': self.tangerine.barcode,
                        'qty': 3,
                        'lot_names': ['tangerine02']
                        }]

        self.assertEqual(sum(picking.mapped('move_line_ids.qty_done')), 0)
        picking.update_picking(product_ids=product_ids1,
                               result_package_name=package.name)
        self.assertEqual(len(picking.move_line_ids), 2)
        first_ml = picking.move_line_ids.filtered(lambda ml: ml.qty_done > 0)
        remaining_ml = picking.move_line_ids - first_ml
        self.assertEqual(first_ml.qty_done, 1)
        self.assertEqual(first_ml.lot_name, 'tangerine01')
        self.assertFalse(remaining_ml.lot_name)

        picking.update_picking(product_ids=product_ids2,
                               result_package_name=package.name)
        self.assertEqual(len(picking.move_line_ids), 2)
        self.assertEqual(remaining_ml.qty_done, 3)
        self.assertEqual(remaining_ml.lot_name, 'tangerine02')

        packaged_move_lines = picking.mapped('move_line_ids').filtered(
            lambda x: x.result_package_id == package)

        self.assertEqual(sum(packaged_move_lines.mapped('qty_done')), 4)
        self.assertEqual(len(packaged_move_lines), 2)

        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')


# NB(ale): more tests for drop off location validation in test_move_line.py

class TestUpdatePickingMarksMoveLinesAsDone(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestUpdatePickingMarksMoveLinesAsDone, cls).setUpClass()
        cls.picking_type_pick.u_target_storage_format = 'product'

    def test01_child_drop_location_success(self):
        """ If the updated destination location is a child of the
            expected dest location of the picking, the picking
            update succeeds.
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_location_01.id, 4)
        create_info = [
            {'product': self.apple,
             'qty': 4,
             'location_dest_id': self.test_output_location_01.id},
            {'product': self.banana,
             'qty': 4,
             'location_dest_id': self.test_output_location_01.id}]

        picking = self.create_picking(self.picking_type_pick,
                                      products_info=create_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        product_ids = [
            {'barcode': self.apple.barcode,
             'qty': 4},
            {'barcode': self.banana.barcode,
             'qty': 4}]

        # The following should trigger the drop location constraint
        # validation without throwing
        picking.move_line_ids.write(
            {'location_dest_id': self.test_output_location_01.id})

        for ml in picking.move_line_ids:
            self.assertEqual(ml.qty_done, 0)

        picking.update_picking(product_ids=product_ids,
                               location_dest_id=self.test_output_location_01.id)
        self.assertEqual(sum([ml.qty_done for ml in picking.move_line_ids]), 8)
        picking.update_picking(validate=True)
        self.assertEqual(picking.state, 'done',
                         'Stock picking is not in state done after validation.')

    def test02_child_drop_location_failure(self):
        """ If the updated destination location is NOT a child of
            the expected dest location of the picking, a validation
            error is thrown after the update_picking() invocation.
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4)
        create_info = [
            {'product': self.apple,
             'qty': 4,
             'location_dest_id': self.test_output_location_01.id}]

        picking = self.create_picking(self.picking_type_pick,
                                      products_info=create_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        product_ids = [
            {'barcode': self.apple.barcode,
             'qty': 4}]
        err = "The location '%s' is not a child of the picking destination location '%s'" \
              % (self.test_location_01.name, picking.location_dest_id.name)

        with self.assertRaises(ValidationError) as e_1:
            picking.move_line_ids.write({'location_dest_id': self.test_location_01.id})

        self.assertEqual(e_1.exception.name, err)
        self.assertEqual(picking.move_lines.quantity_done, 0)

        with self.assertRaises(ValidationError) as e_2:
            picking.update_picking(product_ids=product_ids,
                                   location_dest_id=self.test_location_01.id)

        self.assertEqual(e_2.exception.name, err)

    def test03_child_drop_location_failure_multiple_products(self):
        """ If the updated destination location is NOT a child of
            the expected dest location of the picking, a validation
            error is thrown after the update_picking() invocation
            (case of multiple products).
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_location_01.id, 4)
        create_info = [
            {'product': self.apple,
             'qty': 4,
             'location_dest_id': self.test_output_location_01.id},
            {'product': self.banana,
             'qty': 4,
             'location_dest_id': self.test_output_location_01.id}]

        picking = self.create_picking(self.picking_type_pick,
                                      products_info=create_info,
                                      confirm=True,
                                      assign=True)
        picking = picking.sudo(self.outbound_user)

        product_ids = [
            {'barcode': self.apple.barcode,
             'qty': 4},
            {'barcode': self.banana.barcode,
             'qty': 4}]
        err = "The location '%s' is not a child of the picking destination location '%s'" \
              % (self.test_location_01.name, picking.location_dest_id.name)

        with self.assertRaises(ValidationError) as e_1:
            picking.move_line_ids.write({'location_dest_id': self.test_location_01.id})

        self.assertEqual(e_1.exception.name, err)
        self.assertEqual(sum([p.quantity_done for p in picking.move_lines]), 0)

        with self.assertRaises(ValidationError) as e_2:
            picking.update_picking(product_ids=product_ids,
                                   location_dest_id=self.test_location_01.id)

        self.assertEqual(e_2.exception.name, err)

class TestUpdatePickingExplicitDropOff(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestUpdatePickingExplicitDropOff, cls).setUpClass()
        cls.picking_type_pick.u_target_storage_format = 'pallet_products'

        cls.create_quant(cls.apple.id, cls.test_location_01.id, 4)
        cls.create_quant(cls.banana.id, cls.test_location_01.id, 4)
        cls.create_quant(cls.cherry.id, cls.test_location_01.id, 4)
        create_info = [
            {'product': cls.apple,
             'qty': 4,
             'location_dest_id': cls.test_output_location_01.id},
            {'product': cls.banana,
             'qty': 4,
             'location_dest_id': cls.test_output_location_01.id},
            {'product': cls.cherry,
             'qty': 4,
             'location_dest_id': cls.test_output_location_01.id}]

        cls.picking = cls.create_picking(cls.picking_type_pick,
                                         products_info=create_info,
                                         confirm=True,
                                         assign=True)
        cls.picking = cls.picking.sudo(cls.outbound_user)
        cls.apple_move_line = cls.picking.move_line_ids.filtered(lambda ml: ml.product_id == cls.apple)
        cls.banana_move_line = cls.picking.move_line_ids.filtered(lambda ml: ml.product_id == cls.banana)
        cls.cherry_move_line = cls.picking.move_line_ids.filtered(lambda ml: ml.product_id == cls.cherry)

    def test01_explicit_drop_off_all(self):
        """ Test that update_picking updates the destination location of
            completed move lines and only completed move lines when no products
            are given.
        """
        product_ids = [
            {'barcode': self.apple.barcode,
             'qty': 4},
            {'barcode': self.banana.barcode,
             'qty': 4}]

        self.picking.update_picking(product_ids=product_ids,
                                    result_package_name='UDES100000',
                                    location_dest_id=self.test_output_location_01.id)

        self.assertEqual(self.apple_move_line.location_dest_id,
                         self.test_output_location_01)
        self.assertEqual(self.banana_move_line.location_dest_id,
                         self.test_output_location_01)
        self.assertEqual(self.cherry_move_line.location_dest_id,
                         self.test_output_location_01)

        # Drop off
        self.picking.update_picking(location_dest_id=self.test_output_location_02.id)

        self.assertEqual(self.apple_move_line.location_dest_id,
                         self.test_output_location_02)
        self.assertEqual(self.banana_move_line.location_dest_id,
                         self.test_output_location_02)
        self.assertEqual(self.cherry_move_line.location_dest_id,
                         self.test_output_location_01)

    def test02_explicit_drop_off_by_pallet(self):
        """ Test that update_picking updates the destination location of
            completed move lines with a given destination pallet.
        """
        product_ids_1 = [
            {'barcode': self.apple.barcode,
             'qty': 4},
            {'barcode': self.banana.barcode,
             'qty': 4}]
        product_ids_2 = [
            {'barcode': self.cherry.barcode,
             'qty': 4}]

        self.picking.update_picking(product_ids=product_ids_1,
                                    result_package_name='UDES100000',
                                    location_dest_id=self.test_output_location_01.id)
        self.picking.update_picking(product_ids=product_ids_2,
                                    result_package_name='UDES100001',
                                    location_dest_id=self.test_output_location_01.id)

        self.assertEqual(self.apple_move_line.location_dest_id,
                         self.test_output_location_01)
        self.assertEqual(self.banana_move_line.location_dest_id,
                         self.test_output_location_01)
        self.assertEqual(self.cherry_move_line.location_dest_id,
                         self.test_output_location_01)

        # Drop off first pallet
        self.picking.update_picking(result_package_name='UDES100000',
                                    location_dest_id=self.test_output_location_02.id)

        self.assertEqual(self.apple_move_line.location_dest_id,
                         self.test_output_location_02)
        self.assertEqual(self.banana_move_line.location_dest_id,
                         self.test_output_location_02)
        self.assertEqual(self.cherry_move_line.location_dest_id,
                         self.test_output_location_01)

        # Drop off second pallet
        self.picking.update_picking(result_package_name='UDES100001',
                                    location_dest_id=self.test_output_location_02.id)

        self.assertEqual(self.cherry_move_line.location_dest_id,
                         self.test_output_location_02)
