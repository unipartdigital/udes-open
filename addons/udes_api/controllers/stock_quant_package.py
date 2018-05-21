# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi


class Package(UdesApi):

    @http.route('/api/stock-quant-package/', type='json', methods=['GET'], auth='user')
    def get_package(self, package_id=None, package_name=None, check_reserved=None):
        """ Search for a package by id or name and returns a
            stock.quant.package object that match the given criteria.

            @param (optional) package_id
                The package's id
            @param (optional) package_name
                This is a string that entirely matches the name
            @param (optional) check_reserved:  Boolean (default = false)
                When enabled, checks if the content of the package is reserved,
                in which case an error will be raise.
        """
        Package = request.env['stock.quant.package']
        identifier = package_id or package_name
        if not identifier:
            raise ValidationError(_('You need to provide an id or name for the package.'))

        package = Package.get_package(identifier, no_results=True)
        res = []
        if package:
            if check_reserved:
                package.assert_not_reserved()

            res = package.get_info(extended=True)[0]
        return res

    @http.route('/api/stock-quant-package/<identifier>/suggested-locations',
                type='json', methods=['GET'], auth='user')
    def suggested_locations(self, identifier):
        """ Search for locations which products within a package are currently stored.

            @param identifier
                A package identifier

            Example output:
                { "jsonrpc": "2.0",
                  "result" : [
                    {"id": 1, "name": "Location 1", "barcode": "L00000100"},
                    {"id": 2, "name": "Location 2", "barcode": "L00000200"}
                ]}
        """
        Package = request.env['stock.quant.package']
        Quant = request.env['stock.quant']

        # Get package by identifier
        package = Package.get_package(identifier, no_results=True)

        if package:
            # Get products in that package
            product = package.mapped('quant_ids.product_id')

            if not product:
                raise ValidationError(_('Empty package'))
        else:
            raise ValidationError(_('Invalid package identifier'))

        quants = Quant.search([('product_id', 'in', product.ids)])
        return quants.mapped('location_id') \
                     .filtered(lambda loc: not loc.u_blocked and loc.barcode) \
                     .get_info()
