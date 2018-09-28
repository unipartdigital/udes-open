# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi


class PickingApi(UdesApi):

    @http.route('/api/stock-picking/', type='json', methods=['GET'], auth='user')
    def get_pickings(self, fields_to_fetch=None, **kwargs):
        """ Search for pickings by various criteria and return an
            array of stock.picking objects that match a given criteria.

            @param fields_to_fetch: Array (string)
                Subset of the default returned fields to return.
        """
        Picking = request.env['stock.picking']

        pickings = Picking.get_pickings(**kwargs)

        if 'package_name' in kwargs and pickings.picking_type_id.u_auto_batch_pallet:
            pickings.batch_to_user(request.env.user)

        return pickings.get_info(fields_to_fetch=fields_to_fetch)

    @http.route('/api/stock-picking/', type='json', methods=['POST'], auth='user')
    def create_picking(self, **kwargs):
        """ Old create_internal_transfer
        """
        Picking = request.env['stock.picking']
        picking = Picking.create_picking(**kwargs)
        return picking.get_info()[0]

    @http.route('/api/stock-picking/<ident>', type='json', methods=['POST'], auth='user')
    def update_picking(self, ident, **kwargs):
        """ Old force_validate/validate_operation
        """
        Picking = request.env['stock.picking']
        picking = Picking.browse(int(ident))
        if not picking.exists():
            raise ValidationError(_('Cannot find stock.picking with id %s') % ident)
        picking.update_picking(**kwargs)
        return picking.get_info()[0]

    @http.route('/api/stock-picking/<ident>/is_compatible_package/<package_name>', type='json', methods=['GET'], auth='user')
    def is_compatible_package(self, ident, package_name):
        """ Check if the package name is compatible with the
            picking with id <ident>, i.e., the package name has not been
            used before, only has been used in the same picking and
            it is not in use at stock.
        """
        Picking = request.env['stock.picking']
        picking = Picking.browse(int(ident))
        if not picking.exists():
            raise ValidationError(_('Cannot find stock.picking with id %s') % ident)
        return picking.is_compatible_package(package_name)

    @http.route('/api/stock-picking/<identifier>/suggested-locations',
                type='json', methods=['GET'], auth='user')
    def suggested_locations(self, identifier, package_name=None,
                            move_line_ids=None):
        """ Search suggested locations

            Example output:
                { "jsonrpc": "2.0",
                  "result" : [
                    {"id": 1, "name": "Location 1", "barcode": "L00000100"},
                    {"id": 2, "name": "Location 2", "barcode": "L00000200"}
                ]}
        """
        Package = request.env['stock.quant.package']
        MoveLine = request.env['stock.move.line']
        Picking = request.env['stock.picking']

        picking = Picking.browse(int(identifier))

        kwargs = {}
        if package_name:
            package = Package.get_package(package_name)
            kwargs['package'] = package
        elif move_line_ids:
            kwargs['move_line_ids'] = MoveLine.browse(move_line_ids)
        locations = picking.get_suggested_locations(**kwargs)

        return locations.get_info()
