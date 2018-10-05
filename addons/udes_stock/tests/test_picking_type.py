# -*- coding: utf-8 -*-

from . import common

from odoo.exceptions import ValidationError


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

    def test03_get_suggested_locations_by_product_using_move_lines(self):
        """ All of the suggested locations should have current stock of the
            product, this test uses move_line_ids as parameter instead of
            products.
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

    def test04_get_suggested_locations_by_package(self):
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

    def test05_get_suggested_locations_wrong_move_lines(self):
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

    def test06_get_suggested_locations_by_products_missing_parameter(self):
        """ Validation error raised when trying to suggest locations of a
            picking by products and passing an empty list of move lines.
        """
        self.picking_type_putaway.u_drop_location_policy = 'by_products'

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4, package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_putaway,
                                       products_info=self.pack_4apples_info,
                                       confirm=True,
                                       assign=True)

        with self.assertRaises(ValidationError) as err:
            locations = picking.get_suggested_locations([])

        msg = 'Cannot determine the suggested location: missing move lines'
        self.assertEqual(err.exception.name, msg)
