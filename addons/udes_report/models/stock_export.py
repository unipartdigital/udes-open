# -*- coding: utf-8 -*-

import base64
from collections import OrderedDict
from contextlib import closing
from datetime import datetime
from io import BytesIO
from itertools import groupby
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import xlwt


_logger = logging.getLogger(__name__)
SAVE_DIR = "/home/odoo/"


class StockExport(models.TransientModel):
    _name = 'udes_export.stock_export'
    _description = 'Creates spreadsheets summarising the warehouse stock'

    file_name = fields.Char('Filename')
    file_data = fields.Binary('File')
    date = fields.Date('Date')

    @api.model
    def __get_default_stock_location(self):
        return self.env['stock.location'].search([('name', '=', 'Stock')])

    # @todo: (ale) using Many2many, not One2many; check that
    # @todo: (ale) linking to actual locations, not ids; check that
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

    def run_stock_file_export(self):
        '''
        Creates a stock file summarising the current stock in the
        warehouse. Such file will be in the excel format and contain
        two tabs:
            1) part number, location, pallet ID and quantity;
            2) part number, number of pallets and total quantity.
        '''
        locations = self.included_locations - self.excluded_locations

        if not locations:
            raise UserError(_("The specified list of Stock Locations is empty"))

        Quant = self.env['stock.quant']
        Product = self.env['product.product']
        Location = self.env['stock.location']
        all_quants = Quant.search([('location_id', 'child_of', locations.ids)])
        by_prod = lambda x: x.product_id.id
        by_location = lambda x: x.location_id.id

        get_pallets_by_loc = lambda quant_union: {
            Location.browse(loc): Quant.union(*_quants).mapped('package_id')
            for loc, _quants in groupby(quant_union.sorted(key=by_location),
                                        key=by_location)}

        pallets_by_prod_by_loc = OrderedDict()
        pallets_by_prod = OrderedDict()

        for prod, _quants in groupby(all_quants.sorted(key=by_prod),
                                     key=by_prod):
            quant_prods = Product.browse(prod)
            quants_u = Quant.union(*_quants)
            pallets_by_prod_by_loc[quant_prods] = get_pallets_by_loc(quants_u)
            pallets_by_prod[quant_prods] = quants_u.mapped('package_id')

        def get_prod_qty(prod, pallet):
            contained_quants = Quant.search(
                [('package_id', 'child_of', pallet.ids)])
            prod_quants = contained_quants.filtered(
                lambda x: x.product_id == prod)
            return sum(prod_quants.mapped('quantity'))

        _logger.info(_('Creating Excel file'))
        file_name = 'warehouse_stock_{TIMESTAMP}.xls'.format(
            TIMESTAMP=datetime.now())
        wb = xlwt.Workbook()

        def _create_sheet(sheet_name, columns):
            sheet = wb.add_sheet(sheet_name)
            for col, col_title in enumerate(columns):
                sheet.write(0, col, col_title)
            return sheet

        # 1/2) 'Stock File': one entry for each (prod, pallet) pair

        stock_sheet = _create_sheet('Stock File', ['Part Number',
                                                   'Location',
                                                   'Pallet',
                                                   'Quantity'])

        row = 0
        for prod, pallets_by_location in pallets_by_prod_by_loc.items():
            for location, pallets in pallets_by_location.items():
                for pallet_by_prod in pallets:
                    row += 1
                    stock_sheet.write(row, 0, prod.default_code)
                    stock_sheet.write(row, 1, location.display_name)
                    stock_sheet.write(row, 2, pallet_by_prod.name)
                    stock_sheet.write(row, 3, get_prod_qty(prod, pallet_by_prod))

        # 2/2) 'Stock Summary': one entry for each prod

        summary_sheet = _create_sheet('Stock Summary', ['Part Number',
                                                        'Pallet Count',
                                                        'Quantity'])

        for row, (prod, prod_pallets) in enumerate(pallets_by_prod.items(), 1):
            summary_sheet.write(row, 0, prod.default_code)
            summary_sheet.write(row, 1, len(prod_pallets))
            summary_sheet.write(row, 2, get_prod_qty(prod, prod_pallets))

        self.__write_workbook(wb, file_name, "Stock File")

    def run_movement_file_export(self):
        '''
        Creates movement file, in excel format, summarising the stock
        received and sent for a given date, i.e. goods-in and goods-out
        stock moves done, in two different tabs containing:
            1) Goods In:  Reference, Part number, Pallet, Quantity;
            2) Goods Out: Reference, Part number, Pallet, Quantity.
        '''
        if not self.date:
            raise ValidationError(_("Date not found."))

        self.field_data = False
        self.field_name = False

        Move = self.env['stock.move']
        picking_type_in = self.env.ref('stock.picking_type_in')
        picking_type_out = self.env.ref('stock.picking_type_out')

        # @todo: check: usin union (no dups) instead of addition
        picking_types = picking_type_in | picking_type_out

        moves = Move.search([('state', '=', 'done'),
                             ('picking_type_id', 'in', picking_types.ids),
                             ('date', '>', self.date + " 00:00:00"),
                             ('date', '<', self.date + " 23:59:59")])

        in_moves = moves.filtered(lambda m: m.picking_type_id == picking_type_in)
        out_moves = moves.filtered(lambda m: m.picking_type_id == picking_type_out)

        _logger.info(_('Creating Excel file'))
        file_name = 'warehouse_movemenet_{TIMESTAMP}.xls'.format(
            TIMESTAMP=datetime.now())
        wb = xlwt.Workbook()

        for goods_moves, sheet_name in [(in_moves, "Goods In"),
                                        (out_moves, "Goods Out")]:
            sheet = wb.add_sheet(sheet_name)

            for col, title in [(0, 'Reference'),
                               (1, 'Part number'),
                               (2, 'Pallet'),
                               (3, 'Quantity')]:
                sheet.write(0, col, title)

            row = 0
            for move in goods_moves:
                for move_line in move.mapped('move_line_ids'):
                    row += 1
                    sheet.write(row, 0, move.picking_id.origin)
                    sheet.write(row, 1, move.product_id.display_name)
                    sheet.write(row, 2, move_line.result_package_id.name)
                    sheet.write(row, 3, move_line.qty_done)

        self.__write_workbook(wb, file_name, "Movement File")

    @api.model
    def __write_workbook(self, workbook, file_name, doc_title):
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

        _send_message_to_user(
            self.env['res.users'],
            subject="%s Ready" % doc_title,
            body=_("%s %s is attached.") % (doc_title, file_name),
            attachment=attachment)


# @todo: (ale) consider moving this helper elsewhere
def _send_message_to_user(Users, subject, body,
                          recipients=None,
                          related_rec=None,
                          attachment=None,
                          type='notification'):
    '''
    Sends an odoo message to the specified recipients.
    In case no recipient is specified, the functions sends the
    message to the user itself.

    :param Users: The Users model instance.
    :param subject: Subject of the message.
    :param body: Body text of the message.
    :param recipients: List of res.user recipients. Defaults to current user.
    :param related_rec: Related record.
    :param attachment: ir.attachment to attach to the message.
    :param type: message type. Defaults to Odoo internal notification
    :return:
    '''
    assert Users is not None, "must specify the Users instance"
    Message = Users.env['mail.message']
    Notification = Users.env['mail.notification']

    if recipients is None:
        recipients = [Users.env.user]

    _logger.info("Message to: {RECIPIENTS}\n"
                 "{SUBJECT}\n"
                 "{BODY}\n"
                 "Attached File: {ATTACHMENT}".format(
        RECIPIENTS=[u.name for u in recipients],
        SUBJECT=subject,
        BODY=body,
        ATTACHMENT=attachment.datas_fname or 'None'))

    info = {
        'message_type': type,
        'subject': subject,
        'record_name': subject,
        'body': body,
        'partner_ids': [(4, recip.partner_id.id) for recip in recipients]}

    if related_rec is not None:
        info.update({
            'model': related_rec._name,
            'res_id': related_rec.id})

    if attachment is not None:
        info.update({'attachment_ids': [(4, attachment.id, 0)]})

    msg = Message.create(info)

    if attachment is not None:
        attachment.write(
            {'res_model': msg._name,
             'res_id': msg.id,
             'res_name': msg.record_name})

    for recip in recipients:
        Notification.create(
            {'mail_message_id': msg.id,
             'res_partner_id': recip.partner_id.id})
