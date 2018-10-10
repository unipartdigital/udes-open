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
        push_step = self.search(
            [('location_from_id', 'parent_of', [location.id, ]),
             ('u_push_on_drop', '=', True)])
        # TODO: handle more than one? order by location parent_left to find
        # closest parent to target loc.
        if len(push_step) > 1:
            raise UserError(_('More than one possible push rule found to '
                              'push from %s') % location.display_name)
        return push_step
