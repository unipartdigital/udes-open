# -*- coding: utf-8 -*-
from odoo import models, api, fields, _


class ChangeQuantLocation(models.TransientModel):
    _name = 'change_quant_location'


    def _default_stock(self):
        Users = self.env['res.users']
        warehouse = Users.get_user_warehouse()
        return warehouse.lot_stock_id.id

    location_dest_id = fields.Many2one(
        'stock.location',
        string='New destination location',
    )

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Optional picking type',
    )
    reference = fields.Char('Reference')

    @api.multi
    def create_picking(self):
        self.ensure_one()
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']

        packages = Package.browse(self.env.context['active_ids'])
        quant_ids = packages._get_contained_quants().ids
        location = packages.mapped('location_id')
        if len(location) == 1:
            location_id = location.id
        else:
            location_id = self._default_stock()
        params = {
            'quant_ids': quant_ids,
            'location_id': location_id,
            'picking_type_id': self.picking_type_id.id,
        }
        if self.reference:
            params['origin'] = self.reference

        new_picking = Picking.create_picking(**params)
        # the picking is created with default location_dest_id
        # of the picking type so odoo creates the route if needed
        # after location_dest_id is updated to the specific
        # location set at self.location_dest_id
        if self.location_dest_id:
            new_picking.location_dest_id = self.location_dest_id

        return new_picking.open_stock_picking_form_view()

