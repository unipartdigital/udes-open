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
        """Check that location is forced to match the move_line"""
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
            mls.write({
                'location_dest_id': self.test_location_02.id
            })

    def test17_enforce_preprocessed_location(self):
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
