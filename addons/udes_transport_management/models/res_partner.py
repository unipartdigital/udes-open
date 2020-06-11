# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_driver = fields.Boolean(string='Is a Driver', default=False,
        help="Check if the contact is a driver")
    is_transporter = fields.Boolean(string='Is a Transporter', default=False,
        help="Check if the contact is a transporter")

    # TODO: constrain over is_driver/is_transporter relation
