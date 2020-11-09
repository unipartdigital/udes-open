# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductPackaging(models.Model):
    _inherit = "product.packaging"

    active = fields.Boolean("Active", default=True)

    def _prepare_info(self, fields_to_fetch=None):
        """
            Prepares the following info of the product in self:
            - id: int
            - name: string
            - sequence: int

            @param (optional) fields_to_fetch
                Subset of the default fields to return
        """
        self.ensure_one()

        packaging_info = {
            "id": lambda p: p.id,
            "name": lambda p: p.name,
            "sequence": lambda p: p.sequence,
        }

        if not fields_to_fetch:
            fields_to_fetch = packaging_info.keys()

        return {key: value(self) for key, value in packaging_info.items() if key in fields_to_fetch}

    def get_info(self, **kwargs):
        """
        Return a list with the information of each packaging record in self.
        """
        res = []

        for packaging in self:
            res.append(packaging._prepare_info(**kwargs))

        return res
