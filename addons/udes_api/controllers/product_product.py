# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi

class Product(UdesApi):

    @http.route('/api/product-product/', type='json', methods=['GET'], auth='user')
    def get_product(self, product_id=None, product_name=None, product_barcode=None, fields_to_fetch=None):
        """ Search for a product by id, name or barcode and returns a
            product.product object that match the given criteria.

            @param (optional) product_id
                The product's id
            @param (optional) product_name
                This is a string that entirely matches the name
            @param (optional) product_barcode
                This is a string that entirely matches the barcode
            @param (optional) fields_to_fetch
                Subset of the default fields to return

        """
        Product = request.env['product.product']

        identifier = product_id or product_name or product_barcode
        if not identifier:
            raise ValidationError(
                    _('You need to provide an id, name or barcode for'
                      ' the product.'))

        res = dict()
        product = Product.get_product(identifier, no_results=True)
        if product:
            res = product.get_info(fields_to_fetch=fields_to_fetch)[0]

        return res
