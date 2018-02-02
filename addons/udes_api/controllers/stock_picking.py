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
