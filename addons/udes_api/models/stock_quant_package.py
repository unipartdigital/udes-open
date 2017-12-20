# -*- coding: utf-8 -*-

from odoo import api, models, fields

class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"


    @api.multi
    def _prepare_info(self, extended=False):
        """
            Prepares the following info of the quant in self:
            - id: int
            - name: string

            When extended is True also return:
            - quant_ids: [{stock.quants}]
        """
        self.ensure_one()

        info = {"id": self.id,
                "name": self.name,
               }
        
        if extended:
            info['quants'] = self.quant_ids.get_info()

        return info

    @api.multi
    def get_info(self, extended=False):
        """ Return a list with the information of each package in self.
        """
        res = []
        for pack in self:
            res.append(pack._prepare_info(extended=extended))

        return res
