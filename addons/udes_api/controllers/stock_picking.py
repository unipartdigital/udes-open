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
        return pickings.get_info(fields_to_fetch=fields_to_fetch)

    @http.route('/api/stock-picking/', type='json', methods=['POST'], auth='user')
    def create_picking(self, **kwargs):
        """ Old create_internal_transfer
        """
        Picking = request.env['stock.picking']
        picking = Picking.create_picking(**kwargs)
        return picking.get_info()[0]

    @http.route('/api/stock-picking/<ident>', type='json', methods=['POST'], auth='user')
    def update_picking(self, ident, location_id=None, **kwargs):
        """ Old force_validate/validate_operation
        """
        Picking = request.env['stock.picking']
        picking = Picking.browse(int(ident))
        if not picking.exists():
            raise ValidationError(_('Cannot find stock.picking with id %s') % ident)
        #TODO: validate location_id child of picking.location_id ?
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
