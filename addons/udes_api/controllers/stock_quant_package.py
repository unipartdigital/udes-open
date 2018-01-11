# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi

class Package(UdesApi):

    @http.route('/api/stock-quant-package/', type='json', methods=['GET'], auth='user')
    def get_package(self, id=None, query=None, check_reserved=None):
        """ Search for a package by id or name/barcode and returns a
            stock.quant.package object that match the given criteria.

            @param (optional) id
                The pacakge's id
            @param (optional) query
                This is a string that entirely matches either the name or barcode
            @param (optional) check_reserved:  Boolean (default = false)
                When enabled, checks if the content of the package is reserved,
                in which case an error will be raise.
        """
        Package = request.env['stock.quant.package']
        identifier = id or query
        if not identifier:
            raise ValidationError(_('You need to provide an id or name for the package.'))

        package = Package.get_package(identifier)

        if check_reserved:
            package.assert_not_reserved()

        return package.get_info(extended=True)[0]
