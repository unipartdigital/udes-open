# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

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

    def get_package(self, package_identifier):
        """ Get package from a name (i.e., barcode) or id.
        """
        if isinstance(package_identifier, int):
            domain = [('id', '=', package_identifier)]
        elif isinstance(package_identifier, str):
            domain = [('name', '=', package_identifier)]
        else:
            raise ValidationError(_('Unable to create domain for package search from identifier of type %s') % type(package_identifier))

        results = self.search(domain)
        if not results:
            raise ValidationError(_('Package not found for identifier %s') % str(package_identifier))
        if  len(results) > 1:
            raise ValidationError(_('Too many packages found for identifier %s') % str(package_identifier))

        return results
