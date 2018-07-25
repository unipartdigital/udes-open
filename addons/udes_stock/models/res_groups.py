# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResGroups(models.Model):

    _inherit = 'res.groups'

    u_picking_type_ids = fields.Many2many(
        'stock.picking.type',
        string='Picking types',
        help='Picking types allowed for the group',
    )
