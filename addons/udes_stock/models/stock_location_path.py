# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PushedFlow(models.Model):
    _inherit = "stock.location.path"

    u_push_on_drop = fields.Boolean('Push on drop-off', default=False,
                                    help="When stock is dropped in the "
                                         "from_location of this path, "
                                         "automatically push it onwards.")

    @api.model
    def get_path_from_location(self, location):
        """Find a single stock.location.path for which the given location is
        a valid starting location."""
        push_steps = self.search(
            [('location_from_id', 'parent_of', [location.id, ]),
             ('u_push_on_drop', '=', True)])
        if push_steps:
            return push_steps.sorted(key=lambda p: p.location_from_id.parent_left, reverse=True)[0]
        return self.browse()

    def _apply(self, moves):
        """Do not apply rules with push from drop enabled"""
        if self.u_push_on_drop:
            return
        super()._apply(moves)
