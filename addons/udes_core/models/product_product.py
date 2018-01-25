# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError

class ProductProduct(models.Model):
    _inherit = "product.product"

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility='onchange')

    def _prepare_info(self):
        """
            Prepares the following info of the product in self:
            - id: int
            - barcode: string
            - display_name: string
            - name: string
            - tracking: string
        """
        self.ensure_one()

        return {"id": self.id,
                "barcode": self.barcode,
                "display_name": self.display_name,
                "name": self.display_name,
                "tracking": self.tracking,
               }

    def get_info(self):
        """ Return a list with the information of each product in self.
        """
        res = []
        for prod in self:
            res.append(prod._prepare_info())

        return res

    def get_product(self, product_identifier):
        """ Get product from a name, barcode, or id.
        """
        if isinstance(product_identifier, int):
            domain = [('id', '=', product_identifier)]
        elif isinstance(product_identifier, str):
            domain = ['|', ('barcode', '=', product_identifier),
                           ('name', '=', product_identifier)]
        else:
            raise ValidationError(_('Unable to create domain for product search from identifier of type %s') % type(product_identifier))

        results = self.search(domain)
        if not results:
            raise ValidationError(_('Product not found for identifier %s') % str(product_identifier))
        if  len(results) > 1:
            raise ValidationError(_('Too many products found for identifier %s') % str(product_identifier))

        return results
