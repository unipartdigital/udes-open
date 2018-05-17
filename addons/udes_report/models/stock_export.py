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

    def run_stock_file_export(self, send_file_via='user'):
        '''
        Creates a stock file summarising the current stock in the
        warehouse. Such file will be in the excel format and contain
        two tabs:
            1) part number, location, package ID and quantity;
            2) part number, number of packages and total quantity.
        '''
        locations = self.included_locations - self.excluded_locations

        if not locations:
            raise UserError(_("The specified list of Stock Locations is empty."))

        Quant = self.env['stock.quant']
        Product = self.env['product.product']
        Location = self.env['stock.location']
        all_quants = Quant.search([('location_id', 'child_of', locations.ids)])
        by_prod = lambda x: x.product_id.id
        by_location = lambda x: x.location_id.id
        by_package_name = lambda x: x.package_id.name or ''

        get_quants_by_loc = lambda quant_union: {
            Location.browse(loc): Quant.union(*_quants)
            for loc, _quants in groupby(quant_union.sorted(key=by_location),
                                        key=by_location)}

        quants_by_prod_by_loc = OrderedDict()
        prod_summary = defaultdict(lambda: {'n_pkgs': 0, 'qty': 0})

        for prod, _quants in groupby(all_quants.sorted(key=by_prod),
                                     key=by_prod):
            quant_prods = Product.browse(prod)
            quants_u = Quant.union(*_quants)
            quants_by_prod_by_loc[quant_prods] = get_quants_by_loc(quants_u)

        def get_prod_qty(quants):
            u_quants = Quant.union(*quants)

            print(u_quants,
                  u_quants.mapped('quantity'),
                  sum(u_quants.mapped('quantity')))

            return sum(u_quants.mapped('quantity'))

        _logger.info(_('Creating Excel file'))
        file_name = 'warehouse_stock_{TIMESTAMP}.xls'.format(
            TIMESTAMP=datetime.now())
        wb = xlwt.Workbook()

        # 1/2) 'Stock File': one entry for each (prod, package) pair

        stock_sheet = _create_sheet(wb, 'Stock File', ['Part Number',
                                                       'Location',
                                                       'Package',
                                                       'Quantity'])

        row = 0
        for prod, quants_by_location in quants_by_prod_by_loc.items():
            for location, quants in quants_by_location.items():
                for pkg_name, grouped_quants in groupby(quants,
                                                        key=by_package_name):
                    row += 1
                    qty = get_prod_qty(grouped_quants)

                    stock_sheet.write(row, 0, prod.default_code)
                    stock_sheet.write(row, 1, location.display_name)
                    stock_sheet.write(row, 2, pkg_name)
                    stock_sheet.write(row, 3, qty)

                    prod_summary[prod]['qty'] += qty
                    if pkg_name:
                        prod_summary[prod]['n_pkgs'] += 1

        # 2/2) 'Stock Summary': one entry for each prod

        summary_sheet = _create_sheet(wb, 'Stock Summary', ['Part Number',
                                                            'Package Count',
                                                            'Quantity'])

        for row, (prod, summary) in enumerate(sorted(prod_summary.items()), 1):
            summary_sheet.write(row, 0, prod.name)
            summary_sheet.write(row, 1, summary['n_pkgs'])
            summary_sheet.write(row, 2, summary['qty'])

        self._write_workbook(wb, file_name, "Stock File",
                             send_file_via=send_file_via)

    def run_movement_file_export(self, send_file_via='user'):
        '''
        Creates movement file, in excel format, summarising the stock
        received and sent for a given date, i.e. goods-in and goods-out
        stock moves done, in two different tabs containing:
            1) Goods In:  Reference, Part number, Package, Quantity;
            2) Goods Out: Reference, Part number, Package, Quantity.
        '''
        if not self.date:
            raise UserError(_("Date not specified."))

        self.field_data = False
        self.field_name = False

        Users = self.env['res.users']
        warehouse = Users.get_user_warehouse()
        picking_type_in = warehouse.in_type_id
        picking_type_out = warehouse.out_type_id
        picking_types = picking_type_in | picking_type_out

        Move = self.env['stock.move']
        moves = Move.search([('state', '=', 'done'),
                             ('picking_type_id', 'in', picking_types.ids),
                             ('date', '>', self.date + " 00:00:00"),
                             ('date', '<', self.date + " 23:59:59")])

        in_moves = moves.filtered(lambda m: m.picking_type_id == picking_type_in)
        out_moves = moves.filtered(lambda m: m.picking_type_id == picking_type_out)

        _logger.info(_('Creating Excel file'))
        file_name = 'warehouse_movement_{TIMESTAMP}.xls'.format(
            TIMESTAMP=datetime.now())
        wb = xlwt.Workbook()

        for goods_moves, sheet_name in [(in_moves, "Goods In"),
                                        (out_moves, "Goods Out")]:
            sheet = _create_sheet(wb, sheet_name, ['Reference',
                                                   'Part number',
                                                   'Package',
                                                   'Quantity'])

            row = 0
            for move in goods_moves:
                for move_line in move.mapped('move_line_ids'):
                    row += 1
                    sheet.write(row, 0, move.picking_id.origin)
                    sheet.write(row, 1, move.product_id.display_name)
                    sheet.write(row, 2, move_line.result_package_id.name)
                    sheet.write(row, 3, move_line.qty_done)

        self._write_workbook(wb, file_name, "Movement File",
                             send_file_via=send_file_via)

    @api.model
    def _write_workbook(self, workbook, file_name, doc_title,
                        send_file_via='user'):
        with closing(BytesIO()) as output:
            workbook.save(output)
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
