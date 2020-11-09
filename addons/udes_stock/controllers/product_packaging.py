# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from .main import UdesApi


class ProductPackaging(UdesApi):
    @http.route("/api/product-packaging/", type="json", methods=["GET"], auth="user")
    def get_package_types(self, fields_to_fetch=None):
        """ Return all active product packaging records

            @param (optional) fields_to_fetch
                Subset of the default fields to return
        """
        ProductPackaging = request.env["product.packaging"]

        packaging_records = ProductPackaging.search([])

        return packaging_records.get_info(fields_to_fetch=fields_to_fetch)
