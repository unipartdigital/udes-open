# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility='onchange')

    def _prepare_info(self, fields_to_fetch=None):
        """
            Prepares the following info of the product in self:
            - id: int
            - barcode: string
            - display_name: string
            - name: string
            - tracking: string

            @param fields_to_fetch: array of string
                Subset of the default fields to return
        """
        self.ensure_one()

        info = {"id": lambda p: p.id,
                "barcode": lambda p: p.barcode,
                "display_name": lambda p: p.display_name,
                "name": lambda p: p.display_name,
                "tracking": lambda p: p.tracking,
               }

        if not fields_to_fetch:
            fields_to_fetch = info.keys()

        return {key: value(self) for key, value in info.items() if key in fields_to_fetch}


    def get_info(self, **kwargs):
        """ Return a list with the information of each product in self.
        """
        res = []
        for prod in self:
            res.append(prod._prepare_info(**kwargs))

        return res

    def get_product(self, product_identifier, no_results=False):
        """ Get product from a name, barcode, or id.

            @param no_results: Boolean
                Allows to return empty recordset when the product is
                not found
        """
        if isinstance(product_identifier, int):
            domain = [('id', '=', product_identifier)]
        elif isinstance(product_identifier, str):
            domain = ['|', ('barcode', '=', product_identifier),
                           ('name', '=', product_identifier)]
        else:
            raise ValidationError(_('Unable to create domain for product search from identifier of type %s') % type(product_identifier))

        results = self.search(domain)
        if not results and not no_results:
            raise ValidationError(_('Product not found for identifier %s') % str(product_identifier))
        if  len(results) > 1:
            raise ValidationError(_('Too many products found for identifier %s') % str(product_identifier))

        return results
