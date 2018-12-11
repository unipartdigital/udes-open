# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResGroups(models.Model):

    _inherit = 'res.groups'

    u_view_customers = fields.Boolean(
        string='Customers',
        help='If a user is allowed to view customers',
        default=False,
    )
