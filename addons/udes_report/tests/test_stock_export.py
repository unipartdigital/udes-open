# -*- coding: utf-8 -*-

import datetime
import mock

from odoo.addons.stock.tests.common import TestStockCommon
from odoo.exceptions import UserError


class TestStockExport(TestStockCommon):
    def setUp(self, *args, **kwargs):
        super(TestStockExport, self).setUp()
        Users = self.env['res.users']\
            .with_context({'no_reset_password': True,
                           'mail_create_nosubscribe': True})
        self.test_user = Users.create({
            'name': 'Curt Kirkwood',
            'login': 'ckirkwood',
            'email': 'c.k@example.com',
            'notification_type': 'inbox',
            'groups_id': [(6, 0, [self.env.ref('stock.group_stock_user').id])]})
        self.StockExportObj = \
            self.env['udes_report.stock_export'].sudo(self.test_user)
        self.stock_export = self.StockExportObj.create({})
        self.LocationObj = self.env['stock.location']

    #
    ## Stock
    #

    def test_stock_no_locations(self):
        ''' Stock - should error in case no locations are specified '''
        self.stock_export.included_locations = self.LocationObj.browse()
        self.stock_export.excluded_locations = self.LocationObj.browse()

        with self.assertRaises(UserError) as err:
            self.stock_export.run_stock_file_export()

        self.assertIn('The specified list', str(err.exception))

    def test_stock_all_excluded_locations(self):
        ''' Stock - should error in case all locations are excluded '''
        self.stock_export.included_locations = \
            self.LocationObj.browse(self.stock_location)
        self.stock_export.excluded_locations = \
            self.LocationObj.browse(self.stock_location)

        with self.assertRaises(UserError) as err:
            self.stock_export.run_stock_file_export()

        self.assertIn('The specified list', str(err.exception))

    def test_stock_success(self):
        ''' Stock - should call the write method when locations are given '''
        self.stock_export.included_locations = \
            self.LocationObj.browse(self.stock_location)
        self.stock_export.excluded_locations = self.LocationObj.browse()
        invoked = [False]

        def write_callback(workbook, file_name, doc_title, done=invoked):
            done[0] = True

        with mock.patch.object(self.stock_export, '_write_workbook',
                               new=write_callback):
            self.stock_export.run_stock_file_export()
            self.assertTrue(invoked[0])

    #
    ## Movement
    #

    def test_move_no_date(self):
        ''' Movement - should error in case no date is specified '''
        self.stock_export.date = None

        with self.assertRaises(UserError) as err:
            self.stock_export.run_movement_file_export()

        self.assertEqual('Date not specified.', str(err.exception.name))

    def test_move_success(self):
        ''' Movement - should call the write method '''
        self.stock_export.date = datetime.date.today()
        invoked = [False]

        def write_callback(workbook, file_name, doc_title, done=invoked):
            done[0] = True

        with mock.patch.object(self.stock_export, '_write_workbook',
                               new=write_callback):
            self.stock_export.run_movement_file_export()
            self.assertTrue(invoked[0])
