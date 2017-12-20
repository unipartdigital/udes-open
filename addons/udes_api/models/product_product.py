# -*- coding: utf-8 -*-

from odoo import api, models, fields

class ProductProduct(models.Model):
    _inherit = "product.product"


    @api.multi
    def _prepare_info(self):
        """ TODO: add docstring

            id  int     
            barcode     string  
            display_name    string  A formatted, user-friendly representation of the product
            name    string  
            tracking    string  How the product is tracked in the system. This is used for serial numbers and lots.
        """
        self.ensure_one()

        return {"id": self.id,
                "barcode": self.barcode,
                "display_name": self.display_name,
                "tracking": self.tracking,
               }

    @api.multi
    def get_info(self):
        """ TODO: add docstring
        """
        res = []
        for prod in self:
            res.append(prod._prepare_info())

        return res


