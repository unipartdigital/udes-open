# -*- coding: utf-8 -*-

from . import common

from odoo.exceptions import ValidationError, UserError


class TestPickingType(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestPickingType, cls).setUpClass()
        cls.pack_4apples_info = [
            {'product': cls.apple, 'qty': 4}
        ]
        cls.pack_4apples_3bananas_info = [
            {'product': cls.apple, 'qty': 4},
            {'product': cls.banana, 'qty': 3},
        ]

        cls.tall_category = cls.create_category(name='Tall')
        cls.short_category = cls.create_category(name='Short')
        cls.fast_category = cls.create_category(name='Fast')
        cls.slow_category = cls.create_category(name='Slow')

        cls.short_slow = {
            "u_height_category_id": cls.short_category.id,
            "u_speed_category_id": cls.slow_category.id,
        }

        cls.tall_fast = {
            "u_height_category_id": cls.tall_category.id,
            "u_speed_category_id": cls.fast_category.id,
        }

        cls.apple.write(cls.short_slow)
        cls.banana.write(cls.tall_fast)
        cls.test_location_01.write(cls.short_slow)
        cls.test_location_02.write(cls.tall_fast)

    def setUp(self):
        super(TestPickingType, self).setUp()

        Package = self.env['stock.quant.package']

        self.package_one   = Package.get_package("test_package_one", create=True)
        self.package_two   = Package.get_package("test_package_two", create=True)
        self.package_three = Package.get_package("test_package_three", create=True)
        self.package_four  = Package.get_package("test_package_four", create=True)

    def test01_get_suggested_locations_exact_match(self):
        """ Suggested location should exactly match with location_dest_id of the
            stock.move.line
        """
        self.picking_type_putaway.u_drop_location_policy = 'exactly_match_move_line'
        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_putaway,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)
        mls = picking.move_line_ids
        mls.write({'location_dest_id': self.test_location_01.id})
        location = picking.get_suggested_locations(mls)

        self.assertEqual(location, self.test_location_01)

    def test02_get_suggested_locations_by_product(self):
        """ All of the suggested locations should have current stock of the
            product.
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_products'
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_two.id)
        self.create_quant(self.apple.id, self.test_location_02.id, 4)

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_putaway,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)
        mls = picking.move_line_ids
        locations = picking.get_suggested_locations(mls)

        self.assertEqual(locations, self.test_locations)

    def test03_get_suggested_locations_by_product_single_location(self):
        """ If a single location has the product then only such location
            is suggested.
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_products'
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_two.id)

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_putaway,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)
        mls = picking.move_line_ids
        locations = picking.get_suggested_locations(mls)

        self.assertEqual(locations, self.test_location_01)

    def test04_get_suggested_locations_by_product_empty_lines_suggested(self):
        """ In case no quants are present in the drop locations,
            the empty ones should be suggested.
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_products'
        self.create_quant(self.banana.id, self.test_location_01.id, 2,
                          package_id=self.package_two.id)

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_putaway,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)
        mls = picking.move_line_ids
        locations = picking.get_suggested_locations(mls)

        self.assertEqual(locations, self.test_location_02)

    def test05_get_suggested_locations_by_product_no_lines(self):
        """ In case all locations are already used for other products, no
            location is suggested.
        """
        Location = self.env['stock.location']

        self.picking_type_putaway.u_drop_location_policy = 'by_products'
        self.create_quant(self.banana.id, self.test_location_01.id, 4,
                          package_id=self.package_two.id)
        self.create_quant(self.cherry.id, self.test_location_02.id, 4)

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_three.id)
        picking = self.create_picking(self.picking_type_putaway,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)
        mls = picking.move_line_ids
        locations = picking.get_suggested_locations(mls)


        self.assertEqual(locations, Location.browse())


    def test06_get_suggested_locations_by_package(self):
        """ Suggested locations should be all where the products inside the
            package are at.
            Note that for packages with multiple products it is suggested any
            location where any of the products are at.
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_packages'
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_two.id)
        self.create_quant(self.banana.id, self.test_location_02.id, 4)

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_one.id)
        self.create_quant(self.banana.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          3, package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_putaway,
                            products_info=self.pack_4apples_3bananas_info,
                            confirm=True,
                            assign=True)
        mls = picking.move_line_ids
        locations = picking.get_suggested_locations(mls)

        self.assertEqual(locations, self.test_locations)

    def test07_get_suggested_locations_wrong_move_lines(self):
        """ Validation error raised when trying to suggest locations of a
            picking using move lines of another picking.
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_products'

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_one.id)
        picking1 = self.create_picking(self.picking_type_putaway,
                                       products_info=self.pack_4apples_info,
                                       confirm=True,
                                       assign=True)

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_two.id)
        picking2 = self.create_picking(self.picking_type_putaway,
                                       products_info=self.pack_4apples_info,
                                       confirm=True,
                                       assign=True)

        mls = picking1.move_line_ids

        with self.assertRaises(ValidationError) as err:
            locations = picking2.get_suggested_locations(mls)

        msg = 'Some move lines not found in picking %s to suggest ' \
              'drop off locations for them.' % picking2.name
        self.assertEqual(err.exception.name, msg)

    def test08_get_suggested_locations_by_products_missing_parameter(self):
        """ Validation error raised when trying to suggest locations of a
            picking by products and passing an empty set of move lines.
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_products'

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_putaway,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)

        MoveLine = self.env['stock.move.line']
        with self.assertRaises(ValidationError) as err:
            locations = picking.get_suggested_locations(MoveLine)

        msg = 'Cannot determine the suggested location: missing move lines'
        self.assertEqual(err.exception.name, msg)

    def test07_get_suggested_locations_by_products_locations_blocked(self):
        """Locations which are blocked should not appear in suggestions"""
        self.picking_type_putaway.u_drop_location_policy = 'by_products'

        self.create_quant(
            self.apple.id,
            self.test_location_01.id,
            4,
            package_id=self.package_two.id
        )
        self.create_quant(self.apple.id, self.test_location_02.id, 4)

        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )
        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        self.test_locations.write({
            'u_blocked': True,
            'u_blocked_reason': 'Blocked for testing',
        })

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertNotIn(self.test_locations, locations)

    def test08_get_suggested_locations_by_height_speed(self):
        """Checks that only locations which match height and speed of product
           are suggested
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_height_speed'

        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )
        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertEqual(self.test_location_01, locations)

    def test09_get_suggested_locations_by_height_speed_missing_speed(self):
        """Checks that only locations which match height and speed of product
           are suggested
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_height_speed'

        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.test_location_01.u_speed_category_id = self.fast_category.id

        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertFalse(locations)

    def test10_get_suggested_locations_by_height_speed_missing_height(self):
        """Checks that only locations which match height and speed of product
           are suggested
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_height_speed'

        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.test_location_01.u_height_category_id = self.tall_category

        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertFalse(locations)

    def test11_get_suggested_locations_by_height_speed_blocked(self):
        """Checks blocked locations are not returned"""
        self.picking_type_putaway.u_drop_location_policy = 'by_height_speed'
        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.test_location_01.write({
            'u_blocked': True,
            'u_blocked_reason': 'For testing',
        })

        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertFalse(locations)

    def test12_get_suggested_locations_by_height_speed_full(self):
        """Check full locations are not suggested"""

        self.picking_type_putaway.u_drop_location_policy = 'by_height_speed'

        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.create_quant(self.apple.id, self.test_location_01.id, 4)

        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertFalse(locations)

    def test13_get_suggested_locations_by_height_speed_in_other_picking(self):
        """Check locations which are already assigned to a move line are not
           suggested
        """

        self.picking_type_putaway.write({
            'u_drop_location_policy': 'by_height_speed',
            'u_drop_location_preprocess': True,
        })

        self.test_location_02.write(self.short_slow)

        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_two.id,
        )

        picking1 = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        picking2 = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        locations1 = picking1.get_suggested_locations(picking1.move_line_ids)
        locations2 = picking2.get_suggested_locations(picking2.move_line_ids)
        self.assertNotEqual(locations1, locations2)
        self.assertIn(locations1, self.test_locations)
        self.assertIn(locations2, self.test_locations)

    def test14_get_suggested_locations_by_height_speed_multi_categories(self):
        """Check get suggested throws an error when move lines containing
           products with more than one category
        """

        self.picking_type_putaway.u_drop_location_policy = 'by_height_speed'

        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.create_quant(
            self.banana.id,
            self.picking_type_putaway.default_location_src_id.id,
            3,
            package_id=self.package_one.id,
        )

        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_3bananas_info,
            confirm=True,
            assign=True,
        )

        with self.assertRaises(UserError) as err:
            picking.get_suggested_locations(picking.move_line_ids)

        products = self.apple | self.banana
        msg = 'Move lines with more than category for height(%s) or ' \
              'speed(%s) provided' % (
                  products.mapped('u_height_category_id.name'),
                  products.mapped('u_speed_category_id.name'),
              )

        self.assertEqual(err.exception.name, msg)

    def test15_get_suggested_locations_by_height_speed_prost_process_loc(self):
        """Check that if a location has not been set in preprocessing
           it can be suggested when requested if a location has become
           available
        """
        self.picking_type_putaway.write({
            'u_drop_location_policy': 'by_height_speed',
            'u_drop_location_preprocess': True,
        })
        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.test_location_01.u_speed_category_id = self.fast_category

        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        self.assertEqual(
            picking.move_line_ids.mapped('location_dest_id'),
            picking.picking_type_id.default_location_dest_id,
        )

        self.test_location_01.u_speed_category_id = self.slow_category

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertEqual(locations, self.test_location_01)

    def test16_enforce_exactly_match_move_line(self):
        """Check that location is forced to match the move_line
           in case the constraint is 'enforce'
        """
        self.picking_type_putaway.write({
            'u_drop_location_policy': 'exactly_match_move_line',
            'u_drop_location_constraint': 'enforce',
        })
        self.create_quant(self.apple.id,
                            self.picking_type_putaway.default_location_src_id.id,
                            4, package_id=self.package_one.id)

        picking = self.create_picking(self.picking_type_putaway,
                                        products_info=self.pack_4apples_info,
                                        confirm=True,
                                        assign=True)
        mls = picking.move_line_ids
        mls.write({'location_dest_id': self.test_location_01.id})
        location = picking.get_suggested_locations(mls)
        self.assertEqual(location, self.test_location_01)

        with self.assertRaises(ValidationError):
            mls.write({'location_dest_id': self.test_location_02.id})

    def test17_enforce_with_empty_exactly_match_move_line(self):
        """Check that location can be an empty one if the
           'enforce_with_empty' constraint is used.
        """
        self.picking_type_putaway.write({
            'u_drop_location_policy': 'exactly_match_move_line',
            'u_drop_location_constraint': 'enforce_with_empty',
        })
        self.create_quant(self.apple.id,
                            self.picking_type_putaway.default_location_src_id.id,
                            4, package_id=self.package_one.id)

        picking = self.create_picking(self.picking_type_putaway,
                                        products_info=self.pack_4apples_info,
                                        confirm=True,
                                        assign=True)
        mls = picking.move_line_ids
        mls.write({'location_dest_id': self.test_location_01.id})
        location = picking.get_suggested_locations(mls)
        self.assertEqual(location, self.test_location_01)

        # Expecting no error
        mls.write({'location_dest_id': self.test_location_02.id})

    def test18_enforce_preprocessed_location(self):
        """Check that if a location has not been set in preprocessing
           it can be suggested when requested if a location has become
           available
        """
        self.picking_type_putaway.write({
            'u_drop_location_policy': 'by_height_speed',
            'u_drop_location_preprocess': True,
            'u_drop_location_constraint': 'enforce',
        })
        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.test_location_01.u_speed_category_id = self.slow_category

        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        self.assertEqual(
            picking.move_line_ids.mapped('location_dest_id'),
            self.test_location_01,
        )

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertEqual(locations, self.test_location_01)

        with self.assertRaises(ValidationError):
            picking.move_line_ids.write({
                'location_dest_id': self.test_location_02.id
            })

    def test19_enforce_with_empty_preprocessed_location(self):
        """Check that if a location has not been set in preprocessing
           it can be suggested when requested if a location has become
           available
        """
        self.picking_type_putaway.write({
            'u_drop_location_policy': 'by_height_speed',
            'u_drop_location_preprocess': True,
            'u_drop_location_constraint': 'enforce_with_empty',
        })
        self.create_quant(
            self.apple.id,
            self.picking_type_putaway.default_location_src_id.id,
            4,
            package_id=self.package_one.id,
        )

        self.test_location_01.u_speed_category_id = self.slow_category

        picking = self.create_picking(
            self.picking_type_putaway,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        self.assertEqual(
            picking.move_line_ids.mapped('location_dest_id'),
            self.test_location_01,
        )

        locations = picking.get_suggested_locations(picking.move_line_ids)
        self.assertEqual(locations, self.test_location_01)

        # Expecting no error
        picking.move_line_ids.write({
            'location_dest_id': self.test_location_02.id
        })

    def test20_assert_single_lot_picking_validation_allowed(self):
        """With a picking type set to restrict multi lot pickings, assert
           that picking with only one lot in its move lines can still be
           validated.
        """
        tangerine_qty = 20

        # Set internal transfer to restrict multi lot pickings
        self.picking_type_internal.u_restrict_multi_lot_pickings = True

        # Create lots for tangerine product
        tangerine_lot = self.create_lot(self.tangerine.id, "T1")

        # Create quant for tangerine product
        self.create_quant(
            self.tangerine.id,
            self.test_location_01.id,
            tangerine_qty,
            lot_id = tangerine_lot.id
        )

        tangerine_product_info = {
            'product': self.tangerine,
            'qty': tangerine_qty,
            'location_id': self.test_location_01.id,
            'location_dest_id': self.test_location_02.id
        }

        tangerine_lot_picking = self.create_picking(self.picking_type_internal,
                                        products_info=[tangerine_product_info],
                                        confirm=True, assign=True)

        tangerine_lot_picking_move_lines = tangerine_lot_picking.move_line_ids
        tangerine_lot_picking_lots = tangerine_lot_picking_move_lines.mapped('lot_id')

        # Assert tangerine lot picking has 1 move line which is linked to the tangerine lot
        self.assertEqual(len(tangerine_lot_picking_move_lines), 1)
        self.assertEqual(tangerine_lot_picking_lots, tangerine_lot)

        tangerine_lot_picking_move_lines[0].qty_done = tangerine_qty

        # Validate the tangerine lot picking which should not raise an exception as it contains
        # only a single lot within the move lines
        tangerine_lot_picking.action_done()

        self.assertEqual(tangerine_lot_picking.state, 'done')

    def test21_assert_multi_lot_picking_validation_prevented(self):
        """With a picking type set to restrict multi lot pickings, assert
           that any picking of this type cannot be validated if its move lines
           contain more than 1 unique product lot.
        """
        strawberry_qty = 10
        tangerine_qty = 20

        # Set internal transfer to restrict multi lot pickings
        self.picking_type_internal.u_restrict_multi_lot_pickings = True

        # Set strabwerry tracking to lot instead of serial number
        self.strawberry.tracking = 'lot'

        # Create lots for strawberry and tangerine products
        strawberry_lot = self.create_lot(self.strawberry.id, "S1")
        tangerine_lot = self.create_lot(self.tangerine.id, "T1")

        # Create quants for strawberry and tangerine products
        self.create_quant(
            self.strawberry.id,
            self.test_location_01.id,
            strawberry_qty,
            lot_id = strawberry_lot.id
        )

        self.create_quant(
            self.tangerine.id,
            self.test_location_01.id,
            tangerine_qty,
            lot_id = tangerine_lot.id
        )

        strawberry_product_info = {
            'product': self.strawberry,
            'qty': strawberry_qty,
            'location_id': self.test_location_01.id,
            'location_dest_id': self.test_location_02.id
        }

        tangerine_product_info = {
            'product': self.tangerine,
            'qty': tangerine_qty,
            'location_id': self.test_location_01.id,
            'location_dest_id': self.test_location_02.id
        }

        multi_lot_products_info = [strawberry_product_info, tangerine_product_info]

        # Create, confirm and assign picking for the strawberry and tangerine lots
        multi_lot_picking = self.create_picking(self.picking_type_internal,
                                        products_info=multi_lot_products_info,
                                        confirm=True, assign=True)

        multi_lot_picking_move_lines = multi_lot_picking.move_line_ids
        multi_lot_picking_lots = multi_lot_picking_move_lines.mapped('lot_id')

        # Assert multi lot picking has 2 move lines with 1 each for 
        # the strawberry and tangerine lots
        self.assertEqual(len(multi_lot_picking_move_lines), 2)
        self.assertEqual(multi_lot_picking_lots, (strawberry_lot | tangerine_lot))

        multi_lot_picking_strawberry_move_line = multi_lot_picking_move_lines.filtered(
            lambda ml: ml.product_id == self.strawberry
        )

        multi_lot_picking_tangerine_move_line = (
            multi_lot_picking_move_lines - multi_lot_picking_strawberry_move_line
        )

        multi_lot_picking_strawberry_move_line.qty_done = strawberry_qty
        multi_lot_picking_tangerine_move_line.qty_done = tangerine_qty

        # Validate the multi lot picking which should raise an exception as it contains
        # multiple lots
        expected_exception_message = 'Cannot validate transfer with multiple lots.'
        with self.assertRaisesRegex(ValidationError, expected_exception_message):
            multi_lot_picking.action_done()

    def test22_assert_picking_with_lot_and_no_lot_lines_validation_prevented(self):
        """With a picking type set to restrict multi lot pickings, assert
           that any picking of this type cannot be validated if its move lines
           contain 1 product lot and lines without a lot set.
        """
        apple_qty = 10
        tangerine_qty = 20

        # Set internal transfer to restrict multi lot pickings
        self.picking_type_internal.u_restrict_multi_lot_pickings = True

        # Create lot for tangerine product
        tangerine_lot = self.create_lot(self.tangerine.id, "T1")

        # Create quants for apple and tangerine products
        self.create_quant(
            self.apple.id,
            self.test_location_01.id,
            apple_qty,
        )

        self.create_quant(
            self.tangerine.id,
            self.test_location_01.id,
            tangerine_qty,
            lot_id = tangerine_lot.id
        )

        apple_product_info = {
            'product': self.apple,
            'qty': apple_qty,
            'location_id': self.test_location_01.id,
            'location_dest_id': self.test_location_02.id
        }

        tangerine_product_info = {
            'product': self.tangerine,
            'qty': tangerine_qty,
            'location_id': self.test_location_01.id,
            'location_dest_id': self.test_location_02.id
        }

        mix_lot_products_info = [apple_product_info, tangerine_product_info]

        # Create, confirm and assign picking for the tangerine and empty lots
        mix_lot_picking = self.create_picking(self.picking_type_internal,
                                        products_info=mix_lot_products_info,
                                        confirm=True, assign=True)

        mix_lot_picking_move_lines = mix_lot_picking.move_line_ids
        mix_lot_picking_lots = mix_lot_picking_move_lines.mapped('lot_id')

        # Assert multi lot picking has 2 move lines and only 1 lot for tangerine
        self.assertEqual(len(mix_lot_picking_move_lines), 2)
        self.assertEqual(mix_lot_picking_lots, tangerine_lot)

        tangerine_moveline = mix_lot_picking_move_lines.filtered(
            lambda ml: ml.lot_id == tangerine_lot
        )

        apple_move_line = (
            mix_lot_picking_move_lines - tangerine_moveline
        )

        tangerine_moveline.qty_done = apple_qty
        apple_move_line.qty_done = tangerine_qty

        # Validate the multi lot picking which should raise an exception as it contains
        # multiple lots
        expected_exception_message = 'Cannot validate transfer with both set lot and '
        'empty lot move lines.'

        with self.assertRaisesRegex(ValidationError, expected_exception_message):
            mix_lot_picking.action_done()

    def test23_returns_reserve_pallet_per_picking_in_info(self):
        info = self.picking_type_pick.get_info()
        self.assertIn('u_reserve_pallet_per_picking', info[0])

    def test24_returns_reserve_pallet_per_picking_in_info(self):
        info = self.picking_type_pick.get_info()
        self.assertIn('u_max_reservable_pallets', info[0])
