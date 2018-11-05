# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .main import UdesApi


class Printer(UdesApi):


    # TODO: why this controller module is not in odoo-print?


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
        Printer = request.env['print.printer']
        return Printer.spool_report(object_ids, report_name, copies=copies,
                                    **kwargs)

    @http.route('/api/print-printer/set-user-printer', type='json',
                methods=['POST'], auth='user')
    def set_user_printer(self, barcode):
        """ Sets users default printer.

            @param barcode (string)
                Barcode of the printer you wish to set as user default
        """
        Printer = request.env['print.printer']

        # Check printer exists
        printer = Printer.search([('barcode', '=', barcode)])
        if not printer:
            raise ValidationError(
                _('Cannot find printer with barcode: %s') % barcode)

        return printer.set_user_default()

    # @http.route('/api/print-printer/get-user-printer-settings', type='json',
    #             methods=['GET'], auth='user')
    # def get_user_printer_settings(self, query):
    #     """ Returns the printer settings for the given user.

    #         Request:
    #         the requested settings should be specified as entries of
    #         the `query` dictionary, where keys indicate a given
    #         setting and values give query options & filter criteria
    #         (the format is setting-specific) if applicable (else
    #         ignored).

    #         Response:
    #         the method returns a dictionary with an entry for each
    #         requested setting, where keys are different setting names
    #         and values follow setting-specific formats.

    #         Raises a ValidationError in case of unknown setting.

    #         Supported settings:
    #         - 'configured_printers'
    #             + request: a list of int will specify the picking
    #               types (by IDs) of interest; if an empty list is
    #               given, the response will include the configured
    #               printers info of all picking types;
    #             + response format: a dictionary where keys indicate
    #               different picking type IDs and values are a dict
    #               of boolean values: keys are the printer group
    #               names (of all the groups required for performing
    #               the print operations of a given picking type),
    #               values are True if the user has a printer
    #               configured for that group, False otherwise.

    #         @param query (dictionary)
    #             Specifies the requested settings (see above)
    #     """
    #     # TODO: Probably an overkill, right?
    #     return {}

    @http.route('/api/print-printer/get-user-printer-groups', type='json',
                methods=['GET'], auth='user')
    def get_user_printer_groups(self, picking_type_ids):
        """ Returns inforamtion related to the printers configured
            for the user, organized by printer groups for the
            specified picking types (by IDs, with `picking_type_ids`).

            TODO(ale): is it ok to reply with group names?
            TODO(ale): would it make sense to return the printer barcode
                       instead of a flag? Can we assume that the user
                       will have at most one printer for each group
                       (otherwise return an array)?

            The returned dictionary keys indicate different picking
            type IDs whereas values are dictionary of boolean values:
            keys are the printer group names of all the groups required
            for performing the print operations of the relate picking
            type; values are True if the user has a printer
            configured for that group, False otherwise.

            In case picking_type_ids is an empty list, the returned
            dictionary will include info of all picking types.

            Example:    {
                            1: {
                                "group A": True,
                                "group B": False
                            },
                            5: {
                                "group B": False,
                                "group C": True,
                                "group D": False
                            }
                        }

            Raises a ValidationError in case of unknown picking type.

            @param picking_type_ids Array (int)
                IDs of the picking types of interest
        """
        Users = request.env['res.users']
        Printer = request.env['print.printer']
        PrintStrategy = request.env['udes_stock.strategy.picking.print']

        warehouse = Users.get_user_warehouse()
        all_picking_type_ids = warehouse.get_picking_types().ids

        if not picking_type_ids:
            picking_type_ids = all_picking_type_ids
        else:
            for p in picking_type_ids:
                if p not in all_picking_type_ids:
                    raise ValidationError(_("Unknown picking type ID: %d") % p)

        response = {}
        user_groups = {}

        for picking_type_id in picking_type_ids:
            # TODO(ale): need any arg to "exclude operations via safety catch"?
            groups = PrintStrategy.get_printer_groups(picking_type_id)
            picking_type_groups = {}

            for group in groups:
                # TODO(ale): here we assume that printer groups are orthogonal
                # to picking types, right?
                if group not in user_groups:
                    # TODO(ale): better using group ids for the Printer call?
                    # Printer Groups are Printer, so find a sensible way
                    # to make this work semantically
                    user_groups[group] = \
                        Printer.is_printer_configured_for_user(group)

                picking_type_groups[group] = user_groups[group]

            response[picking_type_id] = picking_type_groups

        return response

    @http.route('/api/print-printer/get-user-printer-groups-mock', type='json',
                methods=['GET'], auth='user')
    def get_user_printer_groups_mock(self, picking_type_ids, success):
        if success:
            return {picking_type_ids[0]: {'A': True, 'B': True, 'C': True}}
        else:
            return {picking_type_ids[0]: {'A': True, 'B': False, 'C': False}}
