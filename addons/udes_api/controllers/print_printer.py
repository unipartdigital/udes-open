# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .main import UdesApi


class Printer(UdesApi):

    @http.route('/api/print-printer/spool-report', type='json',
                methods=['POST'], auth='user')
    def spool_report(self, object_ids, report_name, copies=1, **kwargs):
        """ Prints a report using users default printer.

            @param object_ids Array (int)
                The object ids to add to report
            @param report_name (string)
                Name of the report template
            @param (optional) copies (int, default=1)
                The number of copies to print
            @param (optional) kwargs
                Other data passed to report
        """
        Printer = self.env['print.printer']
        return Printer.spool_report(object_ids, report_name, kwargs,
                                    copies=copies)

    @http.route('/api/print-printer/set-user-printer', type='json',
                methods=['POST'], auth='user')
    def set_user_printer(self, barcode):
        """ Sets users default printer.

            @param barcode (string)
                Barcode of the printer you wish to set as user default
        """
        Printer = self.env['print.printer']

        # Check printer exists
        printer = Printer.search([('barcode', '=', barcode)])
        if not printer:
            raise ValidationError(
                _('Cannot find printer with barcode: %s') % barcode)

        return printer.set_user_default()
