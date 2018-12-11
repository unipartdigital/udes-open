# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ResUser(models.Model):

    _inherit = 'res.users'

    def _compute_allowed_picking_types(self):
        """ User's allowed picking types are the picking types allowed
            by its groups.
        """
        for user in self:
            user.u_picking_type_ids = user.mapped('groups_id.u_picking_type_ids')

    u_picking_type_ids = fields.Many2many(
        'stock.picking.type',
        string='Picking types',
        help='Picking types allowed for the user',
        compute=_compute_allowed_picking_types,
        readonly=True,
    )

    def get_user_warehouse(self):
        """ Get the warehouse of the user by chain of the company
        """
        Warehouse = self.env['stock.warehouse']
        user = self.sudo().search([('id', '=', self.env.uid)])
        if not user:
            raise ValidationError(_('Cannot find user to get warehouse.'))
        warehouse = Warehouse.search([('company_id', '=', user.company_id.id)])
        if not warehouse:
            raise ValidationError(_('Cannot find a warehouse for user'))
        if len(warehouse) > 1:
            raise ValidationError(_('Found multiple warehouses for user'))

        return warehouse
