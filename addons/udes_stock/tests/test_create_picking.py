# -*- coding: utf-8 -*-

from . import common


class TestCreatePicking(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestCreatePicking, cls).setUpClass()
        Picking = cls.env['stock.picking']
        cls.SudoPicking = Picking.sudo(cls.stock_user)

    def test01_create_picking_multiple_quants(self):
        """ Test created because of the bug where canceling and
            scanning again the same package was calling create
            picking with repeated quants.
        """
        quant = self.create_quant(self.apple.id,
                                  self.test_location_01.id,
                                  10,
                                  package_id=self.create_package().id)

        with self.assertRaises(AssertionError) as e:
            self.SudoPicking.create_picking([quant.id, quant.id],
                                            self.test_location_01.id,
                                            picking_type_id=self.picking_type_internal.id,
                                            )
