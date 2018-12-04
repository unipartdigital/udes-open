# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ResUser(models.Model):

    _inherit = 'res.users'

    u_view_customers = fields.Boolean(
        string='Allowed to view customers', default=True)
