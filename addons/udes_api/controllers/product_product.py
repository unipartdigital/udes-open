# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi

class Product(UdesApi):

    @http.route('/api/product-product/', type='json', methods=['GET'], auth='user')
    def get_product(self, id=None, query=None, fields_to_fetch=None):
        """ Search for a product by id or name/barcode and returns a
            product.product object that match the given criteria.

            @param (optional) id
                The product's id
            @param (optional) query
                This is a string that entirely matches either the name or barcode
            @param (optional) fields_to_fetch
                Subset of the default fields to return

        """
        Product = request.env['product.product']

        identifier = id or query
        if not identifier:
            raise ValidationError(
                    _('You need to provide an id, name or barcode for'
                      ' the product.'))

        product = Product.get_product(identifier)

        return product.get_info(fields_to_fetch=fields_to_fetch)[0]
