# -*- coding: utf-8 -*-
# TODO  Import from udes_core
# from odoo.addons.udes_stock.tests.common import StockCase

class TestStockPickingTrailerInfo(StockCase):

    def setUp(self):
        super(TestStockPickingTrailerInfo, self).setUp()
        self.Picking = self.env['stock.picking']
        self.create_quant(self.banana, self.fruit_basket, 20)

    def prepare_trailer_info_for_picking(self):
        return {'u_trailer_num': 123,
                'u_trailer_ident': 'ident',
                'u_trailer_license': 'license',
                'u_trailer_driver': 'driver',
                }

    def prepare_trailer_info_for_trailer(self):
        return {'trailer_num': 123,
                'trailer_ident': 'ident',
                'trailer_license': 'license',
                'trailer_driver': 'driver',
                }

    def test_write_picking_creates_trailer_info(self):
        """ Test that when the related fields are written
            the trailer info is created.
        """
        TrailerInfo = self.env['udes_transport_management.trailer_info']
        picking = self.create_picking(self.picking_type_out, {self.banana: 2}, location_id=self.fruit_basket.id)
        self.assertFalse(picking.u_trailer_info_id)
        info = self.prepare_trailer_info_for_picking()
        picking.write(info)
        self.assertTrue(picking.u_trailer_info_id)
        for field in info:
            self.assertEqual(getattr(picking, field), info[field])

    def test_create_trailer_info(self):
        """ Test that when a trailer info is created for a picking
            the picking is updated with the trailer info id.
        """
        TrailerInfo = self.env['udes_transport_management.trailer_info']

        picking = self.create_picking(self.picking_type_out, {self.banana: 2}, location_id=self.fruit_basket.id)
        self.assertFalse(picking.u_trailer_info_id)
        info = self.prepare_trailer_info_for_trailer()
        info['picking_id'] = picking.id
        TrailerInfo.create(info)
        self.assertTrue(picking.u_trailer_info_id)
        info.pop('picking_id')
        for field in info:
            self.assertEqual(getattr(picking, ("u_"+field)), info[field])





