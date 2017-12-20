# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from .main import UdesApi

class Picking(UdesApi):

    @http.route('/api/stock-picking/', type='json', methods=['GET'], auth='user')
    def get_pickings(self, **kwargs):
        """ Search for pickings by various criteria and return an
            array of stock.picking objects that match a given criteria.
        """
        Picking = request.env['stock.picking']
        pickings = Picking.get_pickings(**kwargs)
        return pickings.get_info()
