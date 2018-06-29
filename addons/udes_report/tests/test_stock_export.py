# -*- coding: utf-8 -*-

import datetime
from unittest import mock

from odoo.addons.udes_core.tests.common import BaseUDES
from odoo.exceptions import UserError

class TestStockExport(BaseUDES):
    def setUp(self, *args, **kwargs):
        super(TestStockExport, self).setUp()
        Package = self.env['stock.quant.package']
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
        empty_locations = self.StockExportObj.env['stock.location']
        self.stock_export.included_locations = empty_locations
        self.stock_export.excluded_locations = empty_locations

        with self.assertRaises(UserError) as err:
            self.stock_export.run_stock_file_export()

        self.assertIn('The specified list', str(err.exception),
                      'Wrong error message')

    def test_stock_all_excluded_locations(self):
        ''' Stock - should error in case all locations are excluded '''
        self.stock_export.included_locations = \
            self.LocationObj.browse(self.stock_location.ids)
        self.stock_export.excluded_locations = \
            self.LocationObj.browse(self.stock_location.ids)

        with self.assertRaises(UserError) as err:
            self.stock_export.run_stock_file_export()

        self.assertIn('The specified list', str(err.exception),
                      'Wrong error message')

    def test_stock_success(self):
        ''' Stock - should call the write method when locations are given '''
        self.stock_export.included_locations = \
            self.LocationObj.browse(self.stock_location.ids)

        #Empty record set
        self.stock_export.excluded_locations = \
            self.StockExportObj.env['stock.location']

        with mock.patch.object(self.stock_export,
                               '_write_workbook',
                               autospec=True):
            self.stock_export.run_stock_file_export()
            self.assertEqual(self.stock_export._write_workbook.call_count, 1,
                             "The function that writes the "
                             "workbook was not invoked")

            _timestr = datetime.datetime.today().strftime('%Y-%m-%d %H:%M')
            self.assertIn('warehouse_stock_{}'.format(_timestr),
                          self.stock_export._write_workbook.call_args[0][1])

    #
    ## Movement
    #

    def test_move_no_date(self):
        ''' Movement - should error in case no date is specified '''
        self.stock_export.date = None

        with self.assertRaises(UserError) as err:
            self.stock_export.run_movement_file_export()

        self.assertEqual('Date not specified.', str(err.exception.name),
                         'Wrong error message')

    def test_move_success(self):
        ''' Movement - should call the write method '''
        self.stock_export.date = datetime.date.today()
        invoked = [False]

        with mock.patch.object(self.stock_export,
                               "_write_workbook",
                               autospec=True):
            self.stock_export.run_movement_file_export()
            self.assertEqual(self.stock_export._write_workbook.call_count, 1,
                             "The function that writes the "
                             "workbook was not invoked")

            _timestr = datetime.datetime.today().strftime("%Y-%m-%d %H:%M")
            self.assertIn("warehouse_movement_{}".format(_timestr),
                          self.stock_export._write_workbook.call_args[0][1])
