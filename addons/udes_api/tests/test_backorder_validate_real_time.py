# -*- coding: utf-8 -*-

from odoo.addons.udes_core.tests import common


class TestRealTimeUpdate(common.BaseUDES):

     @classmethod
     def setUpClass(cls):
          super(TestRealTimeUpdate, cls).setUpClass()
          User = cls.env['res.users']
          user_warehouse = User.get_user_warehouse()
          # Get internal move type
          cls.picking_type_goods_in = user_warehouse.in_type_id
          cls.picking_type_internal = user_warehouse.int_type_id

          cls.picking_type_goods_in.write(
                  {
                    'default_location_src_id': cls.env.ref('stock.stock_location_suppliers').id,
                    'default_location_dest_id': cls.test_location_01.id,
                    'u_target_storage_format': 'pallet_products'
                  })

          cls.picking_type_internal.write(
                  {
                    'default_location_src_id': cls.test_location_01.id,
                    'default_location_dest_id': cls.test_location_02.id,
                    'u_validate_real_time': True,
                    'u_target_storage_format': 'pallet_products'
                  })

          cls.location_stock = cls.picking_type_internal.default_location_src_id

     def test01_picking_type_controls_real_time_update(self):
          """ Checks that a backorder is not created when
              the picking_type.u_validate_real_time is false
          """
          Picking = self.env['stock.picking']
          Package = self.env['stock.quant.package']

          package = Package.get_package('test_package', create=True)
          self.create_quant(self.apple.id, self.location_stock.id, 3, package_id=package.id)

          self.picking_type_internal.u_validate_real_time = False
          create_info = [{'product': self.apple, 'qty': 3}]
          picking = self.create_picking(self.picking_type_internal,
                                        products_info=create_info,
                                        assign=True,
                                        confirm=True)
          picking.update_picking(package_name=package.name)
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
                                      self.location_stock.id,
                                      2, package_id=package_1.id)

          quant_1 = self.create_quant(self.apple.id,
                                      self.location_stock.id,
                                      5, package_id=package_2.id)

          create_info = [{'product': self.apple, 'qty': 7}]
          picking = self.create_picking(self.picking_type_internal,
                                        products_info=create_info,
                                        assign=True,
                                        confirm=True)

          mls_before = picking.move_line_ids
          picking.update_picking(package_name=package_1.name)
          backorders = Picking.search([('backorder_id', '=', picking.id)])
          backorders_done =backorders
          self.assertEqual(len(backorders), 1)
          self.assertEqual(backorders.move_line_ids,
                           mls_before - picking.move_line_ids)
          picking.update_picking(package_name=package_2.name)
          self.assertEqual(picking.state, 'done')

          backorders = Picking.search([('backorder_id', '=', picking.id)])
          backorders -= backorders_done
          self.assertEqual(len(backorders), 0)

     def test03_backorder_created_previous_pickings_imcomplete(self):
          """ Checks that backorder and move is split
              is created when emptying a move with
              incomplete moves in move_orig_ids.
          """
          Package = self.env['stock.quant.package']
          Picking = self.env['stock.picking']

          self.create_simple_inbound_route(self.picking_type_internal)

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

          picking_put.update_picking(package_name=package_1.name)
          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          backorders_done = backorders
          self.assertEqual(len(backorders), 1)
          self.assertEqual(len(picking_put.move_line_ids), 0)
          self.assertTrue(picking_put.state != 'done')

          # Check that after picking_2 completes picking_put completes
          picking_2.update_picking(products_info=products_info_2,
                                   result_package_name=package_2.name)
          picking_2.update_picking(validate=True)

          picking_put.update_picking(package_name=package_2.name)
          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          backorders -= backorders_done
          self.assertEqual(len(backorders), 0)
          self.assertEqual(picking_put.state, 'done')

     def test04_update_move_orig_ids_with_package(self):
          """Checks that move_orig_ids is properly updates
             when stock.move is split for packages.
          """
          Package = self.env['stock.quant.package']
          Picking = self.env['stock.picking']

          self.create_simple_inbound_route(self.picking_type_internal)

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

          picking_put.update_picking(package_name=package_1.name)
          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(len(backorders), 1)
          self.assertEqual(picking_put.move_lines.move_orig_ids, picking_2.move_lines)
          self.assertEqual(backorders.move_lines.move_orig_ids, picking_1.move_lines)

          picking_put.update_picking(package_name=package_2.name)
          self.assertEqual(picking_put.state, 'done')
          backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(backorders, backorders_2)

     def test05_update_move_orig_ids_with_serial_package(self):
          """Checks that move_orig_ids is properly updates
             when stock.move is split for packages
             with serial tracking.
          """
          Package = self.env['stock.quant.package']
          Picking = self.env['stock.picking']

          self.create_simple_inbound_route(self.picking_type_internal)

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

          products_info_1 = [{'product_barcode': self.strawberry.barcode,
                              'qty': 2,
                              'serial_numbers': ['Sn1', 'Sn2'],
                             }]
          picking_1.update_picking(products_info=products_info_1,
                                   result_package_name=package_1.name)
          picking_1.update_picking(validate=True)

          products_info_2 = [{'product_barcode': self.strawberry.barcode,
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

          picking_put.update_picking(package_name=package_1.name)
          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(len(backorders), 1)
          self.assertEqual(picking_put.move_lines.move_orig_ids, picking_2.move_lines)
          self.assertEqual(backorders.move_lines.move_orig_ids, picking_1.move_lines)
          picking_put.update_picking(package_name=package_2.name)
          self.assertEqual(picking_put.state, 'done')
          backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(backorders, backorders_2)

     def test06_update_move_orig_ids_with_serial_product(self):
          """Checks that move_orig_ids is properly updated
             when stock.move is split for a product
             with serial tracking.
          """
          Package = self.env['stock.quant.package']
          Picking = self.env['stock.picking']

          self.picking_type_goods_in.u_target_storage_format = 'product'
          self.picking_type_internal.u_target_storage_format = 'product'

          self.create_simple_inbound_route(self.picking_type_internal)

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

          products_info_1 = [{'product_barcode': self.strawberry.barcode,
                              'qty': 2,
                              'serial_numbers': ['Sn1', 'Sn2'],
                             }]
          picking_1.update_picking(products_info=products_info_1)
          picking_1.update_picking(validate=True)

          products_info_2 = [{'product_barcode': self.strawberry.barcode,
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
          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(len(backorders), 1)
          self.assertEqual(picking_put.move_lines.move_orig_ids, picking_2.move_lines)
          self.assertEqual(backorders.move_lines.move_orig_ids, picking_1.move_lines)
          picking_put.update_picking(products_info=products_info_2)
          self.assertEqual(picking_put.state, 'done')
          backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(backorders, backorders_2)

     def test07_mix_of_products_from_multiple_pickings(self):
          """Performs updates on a mix of packages
             from multiple source pickings.
          """
          Package = self.env['stock.quant.package']
          Picking = self.env['stock.picking']

          self.create_simple_inbound_route(self.picking_type_internal)

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
                                   lambda mv: mv.product_id == self.banana
                                   )
          self.assertTrue(banana_moves.move_orig_ids, picking_2.move_lines)

          picking_put.update_picking(package_name=package_2a.name)

          picking_2_banana_moves = picking_2.move_lines.filtered(
                                        lambda mv: mv.product_id == self.banana
                                        )
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
                                        lambda mv: mv.product_id == self.banana
                                        )
          self.assertEqual(len(banana_moves_before), 1)

          picking_put.update_picking(package_name=package_2b.name)
          banana_moves_after = picking_put.move_lines.filtered(
                                        lambda mv: mv.product_id == self.banana
                                        )
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
                                        lambda mv: mv.product_id == self.strawberry
                                        )
          p2_strawberry_moves = picking_2.move_lines.filtered(
                                             lambda mv: mv.product_id == self.strawberry
                                             )
          # Check the move_orig_id contains the two strawberry move_lines for picks 2 and 3
          self.assertEqual(put_strawberry_moves.move_orig_ids,
                           p2_strawberry_moves + picking_3.move_lines
                          )
          picking_put.update_picking(package_name=package_3.name)

          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          backorders -= backorders_done
          backorders_done += backorders
          put_strawberry_moves = picking_put.move_lines.filtered(
                                        lambda mv: mv.product_id == self.strawberry
                                        )
          self.assertEqual(len(backorders), 1)
          self.assertEqual(backorders.move_lines.move_orig_ids, picking_3.move_lines)
          self.assertEqual(put_strawberry_moves.move_orig_ids, p2_strawberry_moves)

          # Part 4
          # validate package_2c to complete move
          strawberry_moves_before = picking_put.move_lines.filtered(
                              lambda mv: mv.product_id == self.strawberry
                              )
          self.assertEqual(len(strawberry_moves_before), 1)
          picking_put.update_picking(package_name=package_2c.name)

          strawberry_moves_after = picking_put.move_lines.filtered(
                                        lambda mv: mv.product_id == self.strawberry
                                        )
          self.assertEqual(len(strawberry_moves_after), 0)

          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          backorders -= backorders_done
          backorders_done += backorders
          self.assertEqual(len(backorders), 1)
          self.assertEqual(backorders.move_lines, strawberry_moves_before)

          # Part 5
          # complete picking_1 which add move.lines for apples
          apple_moves = picking_put.move_lines.filtered(
                              lambda mv: mv.product_id == self.apple
                              )
          self.assertEqual(len(apple_moves.move_line_ids), 0)
          picking_1.update_picking(validate=True)
          self.assertEqual(len(apple_moves.move_line_ids),
                           len(picking_1.mapped('move_line_ids.result_package_id')))

          # Part 6
          # validate 1a split move
          # same origins
          self.assertTrue(apple_moves.move_orig_ids, picking_1.move_lines)
          picking_put.update_picking(package_name=package_1a.name)

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
          picking_put.update_picking(package_name=package_1b.name)
          self.assertEqual(picking_put.state, 'done')
          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          backorders -= backorders_done
          self.assertEqual(len(backorders), 0)


     def test08_mix_of_products_from_multiple_pickings_multiple_move_update(self):
          """ Tests that mutiple moves within
              the same update are handled
              correctly.
          """
          Package = self.env['stock.quant.package']
          Picking = self.env['stock.picking']

          self.create_simple_inbound_route(self.picking_type_internal)

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
                                        lambda mv: mv.product_id == self.apple
                                        )
          banana_moves = picking_put.move_lines.filtered(
                                        lambda mv: mv.product_id == self.banana
                                        )

          self.assertEqual(len(apple_moves.move_line_ids), 1)
          self.assertEqual(len(banana_moves.move_line_ids), 1)
          apple_mls_before = apple_moves.move_line_ids
          banana_mls_before = banana_moves.move_line_ids

          picking_put.update_picking(package_name=package_1.name)

          self.assertEqual(len(apple_moves.move_line_ids), 0)
          self.assertEqual(len(banana_moves.move_line_ids), 0)

          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(len(backorders), 1)
          self.assertEqual(backorders.move_line_ids,
                           apple_mls_before + banana_mls_before)

          self.assertEqual(backorders.move_lines.mapped('move_orig_ids'),
                           picking_1.move_lines)
          self.assertEqual(picking_put.move_lines.mapped('move_orig_ids'),
                           picking_2.move_lines)


          self.assertEqual(len(apple_moves.move_line_ids), 0)
          self.assertEqual(len(banana_moves.move_line_ids), 0)

          picking_2.update_picking(validate=True)
          self.assertEqual(len(apple_moves.move_line_ids), 1)
          self.assertEqual(len(banana_moves.move_line_ids), 1)

          picking_put.update_picking(package_name=package_2.name)
          self.assertEqual(picking_put.state, 'done')
          backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(backorders, backorders_2)

     def test99_update_move_orig_ids_with_product(self):
          """Checks that move_orig_ids updates as
             expected (not well) when stock.move
             is split for a product without tracking.
          """
          Package = self.env['stock.quant.package']
          Picking = self.env['stock.picking']

          self.picking_type_goods_in.u_target_storage_format = 'product'
          self.picking_type_internal.u_target_storage_format = 'product'

          self.create_simple_inbound_route(self.picking_type_internal)

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

          products_info_1 = [{'product_barcode': self.apple.barcode,
                              'qty': 2,
                             }]
          picking_1.update_picking(products_info=products_info_1)
          picking_1.update_picking(validate=True)

          products_info_2 = [{'product_barcode': self.apple.barcode,
                              'qty': 1,
                             }]
          picking_2.update_picking(products_info=products_info_2)
          picking_2.update_picking(validate=True)

          pick_domain = [('picking_type_id', '=', self.picking_type_internal.id)]
          picking_put = Picking.search(pick_domain)

          self.assertEqual(picking_put.move_lines.move_orig_ids,
                           picking_1.move_lines + picking_2.move_lines)

          picking_put.update_picking(products_info=products_info_1)
          backorders = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(len(backorders), 1)
          self.assertEqual(picking_put.move_lines.move_orig_ids,
                           picking_1.move_lines + picking_2.move_lines)
          self.assertEqual(backorders.move_lines.move_orig_ids,
                           picking_1.move_lines + picking_2.move_lines)
          picking_put.update_picking(products_info=products_info_2)
          self.assertEqual(picking_put.state, 'done')
          backorders_2 = Picking.search([('backorder_id', '=', picking_put.id)])
          self.assertEqual(backorders, backorders_2)
