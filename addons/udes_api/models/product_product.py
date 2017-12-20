# -*- coding: utf-8 -*-

from odoo import api, models, fields

class ProductProduct(models.Model):
    _inherit = "product.product"


    @api.multi
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

    @api.multi
    def get_info(self):
        """ Return a list with the information of each product in self.
        """
        res = []
        for prod in self:
            res.append(prod._prepare_info())

        return res


