# -*- coding: utf-8 -*-

import base64
from collections import OrderedDict, defaultdict
from contextlib import closing
from datetime import datetime
from io import BytesIO
from itertools import groupby
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import xlwt


_logger = logging.getLogger(__name__)
SAVE_DIR = "/home/odoo/"


class StockExport(models.TransientModel):
    _name = 'udes_report.stock_export'
    _description = 'Creates spreadsheets summarising the warehouse stock'

    file_name = fields.Char('Filename')
    file_data = fields.Binary('File')
    date = fields.Date('Date')

    @api.model
    def __get_default_stock_location(self):
        '''
        Propagates possible ValidationErrors if it fails to find
        the current user's warehouse.
        '''
        warehouse = self.env['res.users'].get_user_warehouse()
        return warehouse.lot_stock_id

    included_locations = fields.Many2many(
        comodel_name='stock.location',
        column1='included_locs',
        column2='included_stock_reports',
        relation='included_locations_rel',
        string='Included Stock Locations',
        help='Stock Locations to be included in the stock summary',
        options={'no_create': True},
        default=__get_default_stock_location)

    excluded_locations = fields.Many2many(
        comodel_name='stock.location',
        column1='excluded_locs',
        column2='excluded_stock_reports',
        relation='excluded_locations_rel',
        string='Excluded Stock Locations',
        help='Stock Locations that will be excluded from the stock summary',
        options={'no_create': True})

    def run_stock_file_export(self, context=None, send_file_via='user'):
        '''
        Creates a stock file summarising the current stock in the
        warehouse. Such file will be in the excel format and contain
        two tabs:
            1) part number, location, package ID and quantity;
            2) part number, number of packages and total quantity.
        '''
        file_name = 'warehouse_stock_{TIMESTAMP}.xls'.format(TIMESTAMP=datetime.now())

        data = self._generate_stock_file_data()
        self._write_workbook(file_name, "Stock File", data, send_file_via=send_file_via)

    def _generate_stock_file_data(self):
        '''
        Generate data for the stock file.

        This will contain 2 sheets that may then be exported to any format
        (currently only excel)
        Sheets:
            1) part number, location, package ID and quantity;
            2) part number, number of packages and total quantity.
        '''
        Quant = self.env['stock.quant']
        Product = self.env['product.product']

        locations = self.included_locations - self.excluded_locations
        if not locations:
            raise UserError(_("The specified list of Stock Locations is empty."))

        all_quants = Quant.search([('location_id', 'child_of', locations.ids)])

        quants_by_prod_by_loc = OrderedDict()
        prod_summary = defaultdict(lambda: {'n_pkgs': 0, 'qty': 0})

        for prod, quants in all_quants.groupby('product_id'):
            quants_by_prod_by_loc[prod] = {loc: grouped_quants
                                           for loc, grouped_quants in quants.groupby("location_id")}

        # 1/2) 'Stock File': one entry for each prod, package and lot (if applicable)
        stock_file_data = {"name": 'Stock File'}
        # Determine if lots/serials should be shown on the report
        show_tracking = bool(Product.search([("tracking", "!=", "none")], order="id", limit=1))

        headers = ['Part Number', 'Location', 'Package', 'Quantity']
        if show_tracking:
            headers.insert(3, 'Lot/Serial Number')
        stock_file_data["column_titles"] = headers

        rows = []
        for prod, quants_by_location in quants_by_prod_by_loc.items():
            for location, quants in quants_by_location.items():
                for pkg_name, grouped_quants in quants.groupby(lambda x: x.package_id.name or ''):
                    for lot_name, lot_grouped_quants in grouped_quants.groupby(lambda x:
                                                                               x.lot_id.name or ''):
                        qty = lot_grouped_quants.total_quantity()
                        row = {'Part Number': prod.default_code,
                               'Location': location.display_name,
                               'Package': pkg_name,
                               'Quantity': qty}
                        if show_tracking:
                            row['Lot/Serial Number'] = lot_name
                        rows.append(row)
                        prod_summary[prod]['qty'] += qty
                    if pkg_name:
                        prod_summary[prod]['n_pkgs'] += 1
        stock_file_data['rows'] = rows

        # 2/2) 'Stock Summary': one entry for each prod
        stock_summary = {"name": "Stock Summary"}
        stock_summary["column_titles"] = ['Part Number', 'Package Count', 'Quantity']

        rows = []
        for (prod, summary) in sorted(prod_summary.items(), key=lambda x: x[0].id):
            rows.append({'Part Number': prod.default_code,
                         'Package Count': summary['n_pkgs'],
                         'Quantity': summary['qty']})
        stock_summary['rows'] = rows

        return [stock_file_data, stock_summary]

    def run_movement_file_export(self, context=None, send_file_via='user'):
        '''
        Creates movement file, in excel format, summarising the stock
        received and sent for a given date, i.e. goods-in and goods-out
        stock moves done, in two different tabs containing:
            1) Goods In:  Reference, Part number, Package, Quantity;
            2) Goods Out: Reference, Part number, Package, Quantity.
        '''
        file_name = 'warehouse_movement_{TIMESTAMP}.xls'.format(TIMESTAMP=datetime.now())

        data = self._generate_movement_file_data()
        self._write_workbook(file_name, "Movement File", data, send_file_via=send_file_via)

    def _generate_movement_file_data(self):
        '''
        Creates movement file data summarising the stock
        received and sent for a given date, i.e. goods-in and goods-out
        stock moves done, in two different tabs containing:
            1) Goods In:  Reference, Part number, Package, Quantity;
            2) Goods Out: Reference, Part number, Package, Quantity.
        '''
        Users = self.env['res.users']
        Move = self.env['stock.move']

        if not self.date:
            raise UserError(_("Date not specified."))

        self.field_data = False
        self.field_name = False

        warehouse = Users.get_user_warehouse()
        picking_type_in = warehouse.in_type_id
        picking_type_out = warehouse.out_type_id
        picking_types = picking_type_in | picking_type_out

        moves = Move.search([('state', '=', 'done'),
                             ('picking_type_id', 'in', picking_types.ids),
                             ('date', '>', self.date + " 00:00:00"),
                             ('date', '<', self.date + " 23:59:59")])

        in_moves = moves.filtered(lambda m: m.picking_type_id == picking_type_in)
        out_moves = moves.filtered(lambda m: m.picking_type_id == picking_type_out)

        data = []
        for goods_moves, sheet_name in [(in_moves, "Goods In"), (out_moves, "Goods Out")]:
            move_data = {
                "name": sheet_name,
                "column_titles": ['Reference', 'Part number', 'Package', 'Quantity']
            }
            rows = []
            for move in goods_moves:
                for move_line in move.mapped('move_line_ids'):
                    rows.append(
                        {'Reference': move.picking_id.origin,
                         'Part number': move.product_id.display_name,
                         'Package': move_line.result_package_id.name,
                         'Quantity': move_line.qty_done}
                    )
            move_data['rows'] = rows
            data.append(move_data)

        return data

    @api.model
    def _write_workbook(self, file_name, doc_title, sheets_data, send_file_via="user"):
        """Write data to workbook.

        sheets_data is a list of sheets in dict format. [{sheet1}, {sheet2}, ...]
        Each sheet {name, column_titles, rows} has a "name", a list of "column_titles" and
        "rows"; a list of dicts with keys that match the column_titles
        that contains data for the rows [{r1}, {r2}, ...].
        """
        # Generate workbook from data
        _logger.info(_('Creating Excel file'))
        wb = xlwt.Workbook()
        for sheet_data in sheets_data:
            column_names = sheet_data.get("column_titles")
            sheet = _create_sheet(wb, sheet_data.get("name", "Sheet"), column_names)
            for row_number, row in enumerate(sheet_data["rows"]):
                for column_number, column_name in enumerate(column_names):
                    sheet.write(row_number + 1, column_number, row.get(column_name, ""))

        with closing(BytesIO()) as output:
            wb.save(output)
            data = output.getvalue()

        file_data = base64.b64encode(data)
        self.file_name = file_name
        self.file_data = file_data

        attachment = self.env['ir.attachment'].create(
            {'name': file_name,
             'type': 'binary',
             'datas': file_data,
             'datas_fname': file_name})

        # Send stock file via requested method
        if send_file_via == 'email':
            self._send_email(attachment)
        elif send_file_via == 'user':
            self._send_message_to_user(file_name, doc_title, attachment)
        else:
            _logger.warning(
                _('Stock file was created but '
                  'not sent (send_file_via: %s') % send_file_via)

    def _send_message_to_user(self, doc_title, file_name, attachment):
        '''Send attachement to the user via an intenal message'''
        Users = self.env['res.users']
        Users.send_message_to_user(
            subject="%s Ready" % doc_title,
            body=_("%s %s is attached.") % (doc_title, file_name),
            attachment=attachment,
        )

    def _send_email(self, attachment, email_template=None):
        '''
        Send attachement via email, if email_template is None,
        the automated_stock_email_template is used.
        '''
        Mail = self.env['mail.mail']

        # To allow reuse!
        if email_template is None:
            email_template = self.env.ref(
                'udes_report.automated_stock_email_template'
            )
        # Attachment file
        email_template.write({'attachment_ids': [(6, 0, [attachment.id])]})

        # Makes email to send
        mail_id = email_template.send_mail(self.env.uid)
        mail = Mail.browse([mail_id])
        # Actually sends it
        mail.send()

        # As it auto deletes then exists should be empty
        # but incase this changes I'll check state as well
        if not mail.exists() or mail.state == 'sent':
            _logger.info(_('Stock email sent'))
        # if sending fails odoo will raise its own error

        # Reset email_template attachment
        email_template.write({'attachment_ids': [(6, 0, [])]})

    @api.model
    def send_automated_stock_file(self):
        ''' Sends an email with the stock file attached'''
        Export = self.env['udes_report.stock_export']
        export = Export.create([])
        export.run_stock_file_export(send_file_via='email')

#
# Helpers
#


def _create_sheet(workbook, sheet_name, columns_titles):
    sheet = workbook.add_sheet(sheet_name)
    for col, col_title in enumerate(columns_titles):
        sheet.write(0, col, col_title)
    return sheet
