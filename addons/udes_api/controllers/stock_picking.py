# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi


class Picking(UdesApi):

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

    @http.route('/api/stock-picking/<id>', type='json', methods=['POST'], auth='user')
    def update_picking(self, id, **kwargs):
        """ Old force_validate/validate_operation
        """
        Picking = request.env['stock.picking']
        picking = Picking.browse(int(id))
        if not picking.exists():
            raise ValidationError(_('Cannot find stock.picking with id %s') % id)
        picking.update_picking(**kwargs)
        return picking.get_info()[0]

    @http.route('/api/stock-picking/<id>/is_compatible_package', type='json', methods=['GET'], auth='user')
    def is_compatible_package(self, id, package_name=None):
        """ Check if the package of package_name is compatible with
            the picking in id.
        """
        Picking = request.env['stock.picking']
        picking = Picking.browse(int(id))
        if not picking.exists():
            raise ValidationError(_('Cannot find stock.picking with id %s') % id)
        if not package_name:
            raise ValidationError(_('Missing parameter package_name.'))
        return picking.is_compatible_package(package_name)
