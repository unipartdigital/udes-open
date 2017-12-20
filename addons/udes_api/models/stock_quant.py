# -*- coding: utf-8 -*-

from odoo import api, models, fields

class StockQuant(models.Model):
    _inherit = "stock.quant"


    @api.multi
    def _prepare_info(self):
        """
            Prepares the following info of the quant in self:
            - id: int
            - package_id: {stock.quant.package}
            - product_id: {product.product}
            - quantity: float
            - reserved_quantit: float
        """
        self.ensure_one()

        package_info = False
        if self.package_id:
            package_info = self.package_id.get_info()[0]

        return {"id": self.id,
                "package_id": package_info,
                "product_id": self.product_id.get_info()[0],
                "quantity": self.quantity,
                "reserved_quantity": self.reserved_quantity,
               }

    @api.multi
    def get_info(self):
        """ Return a list with the information of each quant in self.
        """
        res = []
        for quant in self:
            res.append(quant._prepare_info())

        return res
