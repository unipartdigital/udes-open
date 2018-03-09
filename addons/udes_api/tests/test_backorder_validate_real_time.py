    # -*- coding: utf-8 -*-

from odoo.addons.udes_core.tests import common
from odoo.exceptions import ValidationError


class TestRealTimeUpdate(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestRealTimeUpdate, cls).setUpClass()
        User = cls.env['res.users']
        Location = cls.env['stock.location']

        user_warehouse = User.get_user_warehouse()

        # Intermidate location for goods in
        # otherwide infinite loop on pull rules
        cls.recived_location = Location.create({
            'name': "TestReceived",
            'barcode': "LTestReceived",
            'location_id': cls.stock_location.id,
        })

        # Get internal move types
        cls.picking_type_goods_in = user_warehouse.in_type_id
        cls.picking_type_internal = user_warehouse.int_type_id

        cls.picking_type_goods_in.write({
            'default_location_src_id': cls.env.ref('stock.stock_location_suppliers').id,
            'default_location_dest_id': cls.recived_location.id,
            'u_target_storage_format': 'pallet_products',
        })

        cls.picking_type_internal.write({
            'default_location_src_id': cls.recived_location.id,
            'default_location_dest_id': cls.test_location_01.id,
            'u_target_storage_format': 'pallet_products',
            'u_validate_real_time': True,
        })

    def _check_for_incomplete_backorder(self, pickings):
        """ Checks to make sure that there are no incomplete
            backorders which may arise from improperly
            set quantities
        """
        Picking = self.env['stock.picking']
        incomplete_backorders = Picking.search([('state', '!=', 'done'),
                                                ('backorder_id', 'in', pickings.ids)])
        self.assertEqual(len(incomplete_backorders), 0)

    def test01_picking_type_controls_real_time_update(self):
        """ Checks that a backorder is not created when
            the picking_type.u_validate_real_time is false
        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']

        package = Package.get_package('test_package', create=True)
        self.create_quant(self.apple.id, self.recived_location.id,
                          3, package_id=package.id)

        self.picking_type_internal.u_validate_real_time = False
        create_info = [{'product': self.apple, 'qty': 3}]
        picking = self.create_picking(self.picking_type_internal,
                                      products_info=create_info,
                                      assign=True,
                                      confirm=True)
        picking.update_picking(package_name=package.name,
                               location_dest_id=self.test_location_02.id)
        backorders = Picking.search([('backorder_id', '=', picking.id)])
        self.assertEqual(len(backorders), 0)

    def test02_backorder_created_on_update(self):
        """ Checks that when a picking calls
            update_picking a backorder is created
            theck checks that on final update_picking
            the picking is validated
        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']

        package_1 = Package.get_package('test_package1', create=True)
        package_2 = Package.get_package('test_package2', create=True)

        quant_1 = self.create_quant(self.apple.id,
                                    self.recived_location.id,
                                    2, package_id=package_1.id)

        quant_1 = self.create_quant(self.apple.id,
                                    self.recived_location.id,
                                    5, package_id=package_2.id)

        create_info = [{'product': self.apple, 'qty': 7}]
        picking = self.create_picking(self.picking_type_internal,
                                      products_info=create_info,
                                      assign=True,
                                      confirm=True)

        mls_before = picking.move_line_ids
        picking.update_picking(package_name=package_1.name,
                               location_dest_id=self.test_location_02.id)
        backorders = Picking.search([('backorder_id', '=', picking.id)])
        backorders_done = backorders
        self.assertEqual(len(backorders), 1)
        self.assertEqual(backorders.move_line_ids,
                      mls_before - picking.move_line_ids)
        picking.update_picking(package_name=package_2.name,
                               location_dest_id=self.test_location_02.id)
        self.assertEqual(picking.state, 'done')

        backorders = Picking.search([('backorder_id', '=', picking.id)])
        backorders -= backorders_done
        self.assertEqual(len(backorders), 0)
        # This should catch any backorders creating by action_done()
        self._check_for_incomplete_backorder(backorders | picking)

    def test03_backorder_created_previous_pickings_imcomplete(self):
        """ Checks that backorder and move is split
            is created when emptying a move with
            incomplete moves in move_orig_ids.
        """
        Package = self.env['stock.quant.package']
        Picking = self.env['stock.picking']

        self.create_simple_inbound_route(self.picking_type_goods_in,
                                         self.picking_type_internal)

        package_1 = Package.get_package('test_apple1_pkg', create=True)
        package_2 = Package.get_package('test_apple2_pkg', create=True)

        create_info_1 = [{'product': self.apple, 'qty': 5}]
        create_info_2 = [{'product': self.apple, 'qty': 10}]

        picking_1 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_1,
                                        confirm=True)

        picking_2 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_2,
                                        confirm=True)

        products_info_1 = [{'product_barcode': self.apple.barcode, 'qty': 5}]
        products_info_2 = [{'product_barcode': self.apple.barcode, 'qty': 10}]

        picking_1.update_picking(products_info=products_info_1,
                                 result_package_name=package_1.name)
        picking_1.update_picking(validate=True)

        pick_domain = [('picking_type_id', '=', self.picking_type_internal.id)]
        picking_put = Picking.search(pick_domain)

        picking_put.update_picking(package_name=package_1.name,
                                   location_dest_id=self.test_location_02.id)
        backorders = Picking.search([('backorder_id', '=', picking_put.id)])
        backorders_done = backorders
        self.assertEqual(len(backorders), 1)
        self.assertEqual(len(picking_put.move_line_ids), 0)
        self.assertTrue(picking_put.state != 'done')

        # Check that after picking_2 completes picking_put completes
        picking_2.update_picking(products_info=products_info_2,
                                 result_package_name=package_2.name)
        picking_2.update_picking(validate=True)

        picking_put.update_picking(package_name=package_2.name,
                                   location_dest_id=self.test_location_02.id)
        backorders = Picking.search([('backorder_id', '=', picking_put.id)])
        backorders -= backorders_done
        self.assertEqual(len(backorders), 0)
        self.assertEqual(picking_put.state, 'done')
        self._check_for_incomplete_backorder(backorders_done | picking_put)

    def test04_update_move_orig_ids_with_package(self):
        """Checks that move_orig_ids is properly updates
           when stock.move is split for packages.
        """
        Package = self.env['stock.quant.package']
        Picking = self.env['stock.picking']

        self.create_simple_inbound_route(self.picking_type_goods_in,
                                         self.picking_type_internal)

        package_1 = Package.get_package('test_apple1_pkg', create=True)
        package_2 = Package.get_package('test_apple2_pkg', create=True)

        create_info_1 = [{'product': self.apple, 'qty': 5}]
        create_info_2 = [{'product': self.apple, 'qty': 10}]

        picking_1 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_1,
                                        confirm=True)

        picking_2 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_2,
                                        confirm=True)

        products_info_1 = [{'product_barcode': self.apple.barcode, 'qty': 5}]
        picking_1.update_picking(products_info=products_info_1,
                                 result_package_name=package_1.name)
        picking_1.update_picking(validate=True)

        products_info_2 = [{'product_barcode': self.apple.barcode, 'qty': 10}]
        picking_2.update_picking(products_info=products_info_2,
                                 result_package_name=package_2.name)
        picking_2.update_picking(validate=True)

        pick_domain = [('picking_type_id', '=', self.picking_type_internal.id)]
        picking_put = Picking.search(pick_domain)

        self.assertEqual(picking_put.move_lines.move_orig_ids,
                      picking_1.move_lines + picking_2.move_lines)

        picking_put.update_picking(package_name=package_1.name,
                                   location_dest_id=self.test_location_02.id)
        backorders_1 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(len(backorders_1), 1)
        self.assertEqual(picking_put.move_lines.move_orig_ids, picking_2.move_lines)
        self.assertEqual(backorders_1.move_lines.move_orig_ids, picking_1.move_lines)

        picking_put.update_picking(package_name=package_2.name,
                                   location_dest_id=self.test_location_02.id)
        self.assertEqual(picking_put.state, 'done')
        backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(backorders_1, backorders_2)
        self._check_for_incomplete_backorder(backorders_1 | picking_put)

    def test05_update_move_orig_ids_with_serial_package(self):
        """Checks that move_orig_ids is properly updates
           when stock.move is split for packages
           with serial tracking.
        """
        Package = self.env['stock.quant.package']
        Picking = self.env['stock.picking']

        self.create_simple_inbound_route(self.picking_type_goods_in,
                                         self.picking_type_internal)

        package_1 = Package.get_package('test_strawberry1_pkg', create=True)
        package_2 = Package.get_package('test_strawberry2_pkg', create=True)

        create_info_1 = [{'product': self.strawberry, 'qty': 2}]
        create_info_2 = [{'product': self.strawberry, 'qty': 1}]

        picking_1 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_1,
                                        confirm=True)

        picking_2 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_2,
                                        confirm=True)

        products_info_1 = [{
            'product_barcode': self.strawberry.barcode,
            'qty': 2,
            'serial_numbers': ['Sn1', 'Sn2'],
        }]
        picking_1.update_picking(products_info=products_info_1,
                                 result_package_name=package_1.name)
        picking_1.update_picking(validate=True)

        products_info_2 = [{
            'product_barcode': self.strawberry.barcode,
            'qty': 1,
            'serial_numbers': ['Sn3'],
        }]
        picking_2.update_picking(products_info=products_info_2,
                                 result_package_name=package_2.name)
        picking_2.update_picking(validate=True)

        pick_domain = [('picking_type_id', '=', self.picking_type_internal.id)]
        picking_put = Picking.search(pick_domain)

        self.assertEqual(picking_put.move_lines.move_orig_ids,
                      picking_1.move_lines + picking_2.move_lines)

        picking_put.update_picking(package_name=package_1.name,
                                   location_dest_id=self.test_location_02.id)
        backorders_1 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(len(backorders_1), 1)
        self.assertEqual(picking_put.move_lines.move_orig_ids, picking_2.move_lines)
        self.assertEqual(backorders_1.move_lines.move_orig_ids, picking_1.move_lines)
        picking_put.update_picking(package_name=package_2.name,
                                   location_dest_id=self.test_location_02.id)
        self.assertEqual(picking_put.state, 'done')
        backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(backorders_1, backorders_2)

        # This should catch any backorders creating by action_done()
        self._check_for_incomplete_backorder(backorders_1 | picking_put)


    def test06_update_move_orig_ids_with_serial_product(self):
        """Checks that move_orig_ids is properly updated
           when stock.move is split for a product
           with serial tracking.
        """
        Package = self.env['stock.quant.package']
        Picking = self.env['stock.picking']

        self.picking_type_goods_in.u_target_storage_format = 'product'
        self.picking_type_internal.u_target_storage_format = 'product'

        self.create_simple_inbound_route(self.picking_type_goods_in,
                                         self.picking_type_internal)

        package_1 = Package.get_package('test_strawberry1_pkg', create=True)
        package_2 = Package.get_package('test_strawberry2_pkg', create=True)

        create_info_1 = [{'product': self.strawberry, 'qty': 2}]
        create_info_2 = [{'product': self.strawberry, 'qty': 1}]

        picking_1 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_1,
                                        confirm=True)

        picking_2 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_2,
                                        confirm=True)

        products_info_1 = [{
            'product_barcode': self.strawberry.barcode,
            'qty': 2,
            'serial_numbers': ['Sn1', 'Sn2'],
        }]
        picking_1.update_picking(products_info=products_info_1)
        picking_1.update_picking(validate=True)

        products_info_2 = [{
            'product_barcode': self.strawberry.barcode,
            'qty': 1,
            'serial_numbers': ['Sn3'],
        }]
        picking_2.update_picking(products_info=products_info_2)
        picking_2.update_picking(validate=True)

        pick_domain = [('picking_type_id', '=', self.picking_type_internal.id)]
        picking_put = Picking.search(pick_domain)

        self.assertEqual(picking_put.move_lines.move_orig_ids,
                      picking_1.move_lines + picking_2.move_lines)

        picking_put.update_picking(products_info=products_info_1)
        backorders_1 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(len(backorders_1), 1)
        self.assertEqual(picking_put.move_lines.move_orig_ids, picking_2.move_lines)
        self.assertEqual(backorders_1.move_lines.move_orig_ids, picking_1.move_lines)
        picking_put.update_picking(products_info=products_info_2)
        self.assertEqual(picking_put.state, 'done')
        backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(backorders_1, backorders_2)

        # This should catch any backorders creating by action_done()
        self._check_for_incomplete_backorder(backorders_1 | picking_put)

    def test07_mix_of_products_from_multiple_pickings(self):
        """Performs updates on a mix of packages
           from multiple source pickings.
        """
        Package = self.env['stock.quant.package']
        Picking = self.env['stock.picking']

        self.create_simple_inbound_route(self.picking_type_goods_in,
                                         self.picking_type_internal)

        package_1a = Package.get_package('test_apple1_pkg', create=True)
        package_1b = Package.get_package('test_apple2_pkg', create=True)
        package_2a = Package.get_package('test_banana1_pkg', create=True)
        package_2b = Package.get_package('test_banana2_pkg', create=True)
        package_2c = Package.get_package('test_strawberry1_pkg', create=True)
        package_3 = Package.get_package('test_strawberry2_pkg', create=True)

        create_info_1 = [{'product': self.apple, 'qty': 15}]
        create_info_2 = [{'product': self.banana, 'qty': 15},
                      {'product': self.strawberry, 'qty': 2}]
        create_info_3 = [{'product': self.strawberry, 'qty': 2}]

        '''
        Goods in pickings
            1:
                15 apples split into two packages of 5 and 10
            2:
                15 bananas split into two packages of 5 and 10
                2 strawberrys (serial_tracked)
            3:
                2 strawberrys (serial_tracked)
        '''
        picking_1 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_1,
                                        confirm=True)

        picking_2 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_2,
                                        confirm=True)

        picking_3 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_3,
                                        confirm=True)

        picking_put = Picking.search([('picking_type_id', '=', self.picking_type_internal.id)])

        products_info_1a = [{'product_barcode': self.apple.barcode, 'qty': 10}]
        products_info_1b = [{'product_barcode': self.apple.barcode, 'qty': 5}]
        products_info_2a = [{'product_barcode': self.banana.barcode, 'qty': 10}]
        products_info_2b = [{'product_barcode': self.banana.barcode, 'qty': 5}]
        products_info_2c = [{'product_barcode': self.strawberry.barcode, 'qty': 2,
                         'serial_numbers': ['Sn%i' % i for i in range(1,3)]}]
        products_info_3 = [{'product_barcode': self.strawberry.barcode, 'qty': 2,
                         'serial_numbers': ['Sn%i' % i for i in range(3,5)]}]

        picking_1.update_picking(products_info=products_info_1a, result_package_name=package_1a.name)
        picking_1.update_picking(products_info=products_info_1b, result_package_name=package_1b.name)
        #picking 1 is left incomplete
        picking_2.update_picking(products_info=products_info_2a, result_package_name=package_2a.name)
        picking_2.update_picking(products_info=products_info_2b, result_package_name=package_2b.name)
        picking_2.update_picking(products_info=products_info_2c, result_package_name=package_2c.name)
        picking_2.update_picking(validate=True)
        picking_3.update_picking(products_info=products_info_3, result_package_name=package_3.name)
        picking_3.update_picking(validate=True)

        # Part 1
        # validate package_2a and split move becuase of package_2b!
        # move_orig_ids should be same for orignal and new move_line
        banana_moves = picking_put.move_lines.filtered(
                            lambda mv: mv.product_id == self.banana)
        self.assertTrue(banana_moves.move_orig_ids, picking_2.move_lines)

        picking_put.update_picking(package_name=package_2a.name,
                                   location_dest_id=self.test_location_02.id)

        picking_2_banana_moves = picking_2.move_lines.filtered(
                                lambda mv: mv.product_id == self.banana)
        self.assertEqual(banana_moves.move_orig_ids, picking_2_banana_moves)

        backorders = Picking.search([('backorder_id', '=', picking_put.id)])
        # save processed backorders so we can remove them from later sets
        backorders_done = backorders
        # one update one backorder!
        self.assertEqual(len(backorders), 1)
        self.assertEqual(backorders.move_lines.move_orig_ids, picking_2_banana_moves)

        # Part 2
        # validate package_2c to complete move
        banana_moves_before = picking_put.move_lines.filtered(
                                lambda mv: mv.product_id == self.banana)
        self.assertEqual(len(banana_moves_before), 1)

        picking_put.update_picking(package_name=package_2b.name,
                                   location_dest_id=self.test_location_02.id)
        banana_moves_after = picking_put.move_lines.filtered(
                                lambda mv: mv.product_id == self.banana)
        # move should be complete and therefore is removed from picking_put
        self.assertEqual(len(banana_moves_after), 0)

        backorders = Picking.search([('backorder_id', '=', picking_put.id)])
        backorders -= backorders_done
        backorders_done += backorders
        self.assertEqual(len(backorders), 1)
        self.assertEqual(backorders.move_lines, banana_moves_before)

        # Part 3
        # validate package_3 which will split move becuase pacakge_2c
        # should spit move_orig_ids
        put_strawberry_moves = picking_put.move_lines.filtered(
                                    lambda mv: mv.product_id == self.strawberry)
        p2_strawberry_moves = picking_2.move_lines.filtered(
                                    lambda mv: mv.product_id == self.strawberry)
        # Check the move_orig_id contains the two strawberry move_lines for picks 2 and 3
        self.assertEqual(put_strawberry_moves.move_orig_ids,
                      p2_strawberry_moves + picking_3.move_lines)
        picking_put.update_picking(package_name=package_3.name,
                                   location_dest_id=self.test_location_02.id)


        backorders = Picking.search([('backorder_id', '=', picking_put.id)])
        backorders -= backorders_done
        backorders_done += backorders
        put_strawberry_moves = picking_put.move_lines.filtered(
                                    lambda mv: mv.product_id == self.strawberry)
        self.assertEqual(len(backorders), 1)
        self.assertEqual(len(backorders.mapped('move_line_ids')), 2)
        self.assertEqual(backorders.move_lines.move_orig_ids, picking_3.move_lines)
        self.assertEqual(put_strawberry_moves.move_orig_ids, p2_strawberry_moves)

        # Part 4
        # validate package_2c to complete move
        strawberry_moves_before = picking_put.move_lines.filtered(
                        lambda mv: mv.product_id == self.strawberry)
        self.assertEqual(len(strawberry_moves_before), 1)
        picking_put.update_picking(package_name=package_2c.name,
                                   location_dest_id=self.test_location_02.id)

        strawberry_moves_after = picking_put.move_lines.filtered(
                                        lambda mv: mv.product_id == self.strawberry)
        self.assertEqual(len(strawberry_moves_after), 0)

        backorders = Picking.search([('backorder_id', '=', picking_put.id)])
        backorders -= backorders_done
        backorders_done += backorders
        self.assertEqual(len(backorders), 1)
        self.assertEqual(backorders.move_lines, strawberry_moves_before)

        # Part 5
        # complete picking_1 which add move.lines for apples
        apple_moves = picking_put.move_lines.filtered(
                        lambda mv: mv.product_id == self.apple)
        self.assertEqual(len(apple_moves.move_line_ids), 0)
        picking_1.update_picking(validate=True)
        self.assertEqual(len(apple_moves.move_line_ids),
                         len(picking_1.mapped('move_line_ids.result_package_id')))

        # Part 6
        # validate 1a split move
        # same origins
        self.assertTrue(apple_moves.move_orig_ids, picking_1.move_lines)
        picking_put.update_picking(package_name=package_1a.name,
                                   location_dest_id=self.test_location_02.id)

        backorders = Picking.search([('backorder_id', '=', picking_put.id)])
        backorders -= backorders_done
        backorders_done += backorders
        self.assertEqual(len(backorders), 1)

        self.assertEqual(backorders.move_lines.move_orig_ids,
                      picking_1.move_lines)

        self.assertEqual(picking_put.move_lines.move_orig_ids,
                      picking_1.move_lines)

        # Part 7
        # validate 1b complete move and picking
        picking_put.update_picking(package_name=package_1b.name,
                                   location_dest_id=self.test_location_02.id)
        self.assertEqual(picking_put.state, 'done')
        backorders = Picking.search([('backorder_id', '=', picking_put.id)])
        backorders -= backorders_done
        self.assertEqual(len(backorders), 0)
        # This should catch any backorders creating by action_done()
        self._check_for_incomplete_backorder(backorders_done | picking_put)

    def test08_mix_of_products_from_multiple_pickings_multiple_move_update(self):
        """ Tests that mutiple moves within
            the same update are handled
            correctly.
        """
        Package = self.env['stock.quant.package']
        Picking = self.env['stock.picking']

        self.create_simple_inbound_route(self.picking_type_goods_in,
                                         self.picking_type_internal)

        package_1 = Package.get_package('test_package1', create=True)
        package_2 = Package.get_package('test_package2', create=True)

        create_info_1 = [{'product': self.apple, 'qty': 10},
                         {'product': self.banana, 'qty': 5}]
        create_info_2 = [{'product': self.apple, 'qty': 5},
                         {'product': self.banana, 'qty': 10}]


        picking_1 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_1,
                                        confirm=True)
        picking_2 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_2,
                                        confirm=True)

        picking_put = Picking.search([('picking_type_id', '=', self.picking_type_internal.id)])

        products_info_1 = [{'product_barcode': self.apple.barcode, 'qty': 10},
                        {'product_barcode': self.banana.barcode, 'qty': 5}]
        products_info_2 = [{'product_barcode': self.apple.barcode, 'qty': 5},
                        {'product_barcode': self.banana.barcode, 'qty': 10}]

        picking_1.update_picking(products_info=products_info_1,
                                 result_package_name=package_1.name)
        picking_1.update_picking(validate=True)
        picking_2.update_picking(products_info=products_info_2,
                                 result_package_name=package_2.name)
        # Leave picking_2 not validated for now

        apple_moves = picking_put.move_lines.filtered(
                                lambda mv: mv.product_id == self.apple)
        banana_moves = picking_put.move_lines.filtered(
                                lambda mv: mv.product_id == self.banana)

        self.assertEqual(len(apple_moves.move_line_ids), 1)
        self.assertEqual(len(banana_moves.move_line_ids), 1)
        apple_mls_before = apple_moves.move_line_ids
        banana_mls_before = banana_moves.move_line_ids

        picking_put.update_picking(package_name=package_1.name,
                                   location_dest_id=self.test_location_02.id)

        self.assertEqual(len(apple_moves.move_line_ids), 0)
        self.assertEqual(len(banana_moves.move_line_ids), 0)

        backorders_1 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(len(backorders_1), 1)
        self.assertEqual(backorders_1.move_line_ids,
                      apple_mls_before + banana_mls_before)

        self.assertEqual(backorders_1.move_lines.mapped('move_orig_ids'),
                         picking_1.move_lines)
        self.assertEqual(picking_put.move_lines.mapped('move_orig_ids'),
                         picking_2.move_lines)

        self.assertEqual(len(apple_moves.move_line_ids), 0)
        self.assertEqual(len(banana_moves.move_line_ids), 0)

        picking_2.update_picking(validate=True)
        self.assertEqual(len(apple_moves.move_line_ids), 1)
        self.assertEqual(len(banana_moves.move_line_ids), 1)

        picking_put.update_picking(package_name=package_2.name,
                                   location_dest_id=self.test_location_02.id)
        self.assertEqual(picking_put.state, 'done')
        backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
        # Only one backorder has been made
        self.assertEqual(backorders_1, backorders_2)
        # This should catch any backorders creating by action_done()
        self._check_for_incomplete_backorder(backorders_1 | picking_put)

    def test09_update_move_orig_ids_with_product(self):
        """Checks that move_orig_ids updates as
           expected (not well) when stock.move
           is split for a product without tracking.
        """
        Package = self.env['stock.quant.package']
        Picking = self.env['stock.picking']

        self.picking_type_goods_in.u_target_storage_format = 'product'
        self.picking_type_internal.u_target_storage_format = 'product'

        self.create_simple_inbound_route(self.picking_type_goods_in,
                                         self.picking_type_internal)

        package_1 = Package.get_package('test_apple1_pkg', create=True)
        package_2 = Package.get_package('test_apple2_pkg', create=True)

        create_info_1 = [{'product': self.apple, 'qty': 2}]
        create_info_2 = [{'product': self.apple, 'qty': 1}]

        picking_1 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_1,
                                        confirm=True)

        picking_2 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info_2,
                                        confirm=True)

        products_info_1 = [{
            'product_barcode': self.apple.barcode,
            'qty': 2,
        }]
        picking_1.update_picking(products_info=products_info_1)
        picking_1.update_picking(validate=True)

        products_info_2 = [{
            'product_barcode': self.apple.barcode,
            'qty': 1,
        }]
        picking_2.update_picking(products_info=products_info_2)
        picking_2.update_picking(validate=True)

        pick_domain = [('picking_type_id', '=', self.picking_type_internal.id)]
        picking_put = Picking.search(pick_domain)

        self.assertEqual(picking_put.move_lines.move_orig_ids,
                      picking_1.move_lines + picking_2.move_lines)

        picking_put.update_picking(products_info=products_info_1)
        backorders_1 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(len(backorders_1), 1)

        combined_lines = picking_1.move_lines + picking_2.move_lines
        self.assertEqual(picking_put.move_lines.move_orig_ids,
                      combined_lines)
        self.assertEqual(backorders_1.move_lines.move_orig_ids,
                      combined_lines)
        picking_put.update_picking(products_info=products_info_2)
        self.assertEqual(picking_put.state, 'done')
        backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
        self.assertEqual(backorders_1, backorders_2)
        # This should catch any backorders creating by action_done()
        self._check_for_incomplete_backorder(backorders_1 | picking_put)

    def test10_check_validation_error_on_empty_mls(self):
        """Checks that correct error is thrown if
           there is move lines to process
        """
        Picking = self.env['stock.picking']
        MoveLine = self.env['stock.move.line']
        create_info = [{'product': self.apple, 'qty': 1}]
        # picking type goods in so I don't have to create quants
        # for this test the picking doesn't matter
        # just has to be a singleton
        picking = self.create_picking(self.picking_type_goods_in,
                                      products_info=create_info,
                                      confirm=True)


        expected_error_msg = 'There is no move lines within ' \
                         'picking %s to backorder' % picking.name

        empty_mls = MoveLine.browse()
        with self.assertRaises(ValidationError) as e:
            picking._create_backorder(empty_mls)
        self.assertEqual(e.exception.name, expected_error_msg,
                        'No/Incorrect error message was thrown')

    def test11_check_validation_error_on_other_pickings_mls(self):
        """Checks that correct error is thrown if
           there is move lines to process
        """
        Picking = self.env['stock.picking']
        MoveLine = self.env['stock.move.line']
        create_info = [{'product': self.apple, 'qty': 1}]
        # picking type goods in so I don't have to create quants
        # for this test the picking doesn't matter
        # just has to be a singleton
        picking_1 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info,
                                        confirm=True)

        picking_2 = self.create_picking(self.picking_type_goods_in,
                                        products_info=create_info,
                                        confirm=True)


        expected_error_msg = 'There is no move lines within ' \
                         'picking %s to backorder' % picking_1.name

        with self.assertRaises(ValidationError) as e:
            picking_1._create_backorder(picking_2.move_line_ids)
        self.assertEqual(e.exception.name, expected_error_msg,
                     'No/Incorrect error message was thrown')
