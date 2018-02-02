# -*- coding: utf-8 -*-

from odoo import models


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def _prepare_info(self, extended=False, **kwargs):
        """
            Prepares the following extra info of the package in self
            - package_id: parent package of self
            - children_ids: children packages of self
        """
        info = super(StockQuantPackage, self)._prepare_info(extended=extended, **kwargs)

        if self.package_id:
            info['package_id'] = self.package_id.id
        if self.children_ids:
            if extended:
                info['children_ids'] = self.children_ids.get_info(extended=extended, **kwargs)
            else:
                info['children_ids'] = self.children_ids.ids

        return info
