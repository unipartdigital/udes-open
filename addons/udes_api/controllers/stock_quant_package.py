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

        package = Package.get_package(identifier)

        if check_reserved:
            package.assert_not_reserved()

        return package.get_info(extended=True)[0]
