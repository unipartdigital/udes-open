# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from .main import UdesApi


class ControllerLocationCategory(UdesApi):

    @http.route('/api/stock-location-category/', type='json',
                methods=['GET'], auth='user')
    def get_location_categories(self):
        """ Gets all the location categories with a boolean flag to show if that
            category is assigned to the current user."""
        Users = request.env['res.users']
        LocationCategory = request.env['stock.location.category']

        user_category_ids = Users.get_user_location_categories().ids
        categories = LocationCategory.search([]).get_info()
        for category in categories:
            category['by_user'] = category['id'] in user_category_ids

        return categories

    @http.route('/api/stock-location-category/set-user-categories', type='json',
                methods=['POST'], auth='user')
    def set_user_categories(self, category_ids):
        """ Sets users location categories.

            @param category_ids (list of int)
                Ids of the location categories to be assigned to the user
        """
        Users = request.env['res.users']
        return Users.set_user_location_categories(category_ids)
