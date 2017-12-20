# -*- coding: utf-8 -*-

from odoo import api, models, fields

class StockQuant(models.Model):
    _inherit = "stock.quant"


    @api.multi
    def _prepare_info(self):
        """ TODO: add docstring

            id  int     
            package_id  stock.quant.package     (see representation of the packages below)
            product_id  product.product     (see representation of the products above)
            quantity    float   The physical quantity of the stock
            reserved_quantity   float   The number of this quantity that has been reserved
        """
        self.ensure_one()

        info = {"id": self.id,
                "package_id": self.package_id.get_info()[0],
                "product_id": self.product_id.get_info()[0],
                "quantity": self.quantity,
                "reserved_quantity": self.reserved_quantity,
               }

        return info

    @api.multi
    def get_info(self):
        """ TODO: add docstring
        """
        res = []
        for quant in self:
            res.append(quant._prepare_info())

        return res
