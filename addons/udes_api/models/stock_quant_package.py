# -*- coding: utf-8 -*-

from odoo import models


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def assert_not_reserved(self):
        """ Check that the content of the package is reserved, in that
        case raise an error.
        """
        self.ensure_one()
        if self.children_ids:
            self.mapped('children_quant_ids').assert_not_reserved()
        else:
            super(StockQuantPackage, self).assert_not_reserved()

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
            info['children_ids'] = self.children_ids.get_info(extended=extended, **kwargs)

        return info
