# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Location(models.Model):

    _inherit = "stock.location"

    def get_empty_children(self, usage=("internal",)):
        return self.search(
            [
                ("id", "child_of", self.id),
                ("usage", "in", usage),
                ("quant_ids", "=", False),
                ("id", "!=", self.id),
            ]
        )
