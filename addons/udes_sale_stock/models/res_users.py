# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUser(models.Model):

    _inherit = 'res.users'

    def _compute_allowed_to_view_customers(self):
        """ User's allowed to view customers if its group is.
        """
        for user in self:
            user.u_view_customers = all(
                user.mapped('groups_id.u_view_customers'))

    u_view_customers = fields.Boolean(
        string='Allowed to view customers',
        help='If a user is allowed to view customers',
        compute=_compute_allowed_to_view_customers,
        readonly=True,
    )
