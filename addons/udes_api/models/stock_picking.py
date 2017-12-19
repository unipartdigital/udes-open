# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = "stock.picking"


    def get_pickings(self,
                     origin=None,
                     package_barcode=None,
                     states=None,
                     allops=None,
                     location_id=None,
                     product_id=None,
                     backorder_id=None,
                     result_package_id=None,
                     picking_priorities=None,
                     picking_ids=None,
                     bulky=None):

        """
                
* @param (optional) location_id is set then only internal transfers acting on that location are considered.
        In all cases, if states is set then only pickings in those states are
        considered.
* (IGNORE FOR NOW) @param (optional) allops: Boolean. (default=True). If True, all pack operations are included.
                       If False, only pack operations that are for the pallet
                       identified by param pallet (and it's sub-packages) are
                       included.
* @param (optional) picking_priorities: When supplied all pickings of set priorities
                        and :states will be searched and returned
* @param (optional) picking_ids: When supplied pickings of the supplied picking ids
                        will be searched and returned.
                        If used in conjunction with priorities then only those
                        pickings of those ids will be returned.
* @param (optional) bulky (Boolean): This is used in conjunction with the picking_priorities
                        parameter to return pickings that have bulky items
* @param (NO LONGER USED - REMOVE) (optional)  use_list_data: Decides whether the _list_data function is used when returning data




        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']

        pickings = Picking.browse()
        domain = []
        use_states = True

        if states is None:
            states = ['draft', 'cancel', 'waiting',
                      'confirmed', 'assigned', 'done']
        if self:
            pickings = self
        elif origin:
            domain = [('origin', '=', origin)]
        elif backorder_id:
            domain = [('backorder_id', '=', backorder_id)]
        elif result_package_id:
            domain = [('move_line_ids.result_package_id', '=', result_package_id)]
        elif product_id:
            if not location_id:
                raise ValidationError(_("Please supply a location_id"))
            domain = [('move_line_ids.product_id', '=', product_id),
                      ('move_line_ids.location_id', '=', location_id)]
        elif package_barcode:
            package = Package.search([('name', '=', package_barcode)])
            # TODO: change = to child_of when we add package hierachy ?
            domain = ['|', ('move_line_ids.package_id', '=', package.id),
                           ('move_line_ids.result_package_id', '=', package.id)]
            """
            list_data_filters['stock_pack_operations'] = {'self': {'package_id': pallet.id}}
            if allops:
                list_data_filters['stock_pack_operations']['allops'] = True
            """

        else:
            raise ValidationError(_('No valid options provided.'))

        if use_states:
            domain.append(('state', 'in', states))


        print("######")
        print(domain)
        if domain:
            pickings = Picking.search(domain)

        """
        elif picking_priorities:
            picking_type_pick = self.env['stock.picking.type'].sudo().get_pick_type()
            domain = [
                ('priority', 'in', picking_priorities),
                ('picking_type_id', '=', picking_type_pick.id),
                ('state', 'in', states),
                ('wave_id', '=', False),
            ]
            if picking_ids is not None:
                domain.append(('id', 'in', picking_ids))
            pickings = self.search(domain, order='priority desc, min_date, id')
            if bulky is not None:
                pickings = pickings.filtered(lambda p: p.u_contains_bulky == bulky)
        elif location_id:
            # TODO: add filter to look for the user id?
            pickings = self.env['stock.picking'].search([
                ('location_id', '=', location_id),
                ('state', 'in', states),
                ('picking_type_id', '=', self.env.ref('stock.picking_type_internal').id)
            ])
        elif picking_ids:
            pickings = self.env['stock.picking'].browse(picking_ids)
            pickings = pickings.filtered(lambda r: r.state in states)
        """
        return pickings



    @api.one
    def get_info(self):
        """
        """
        return {'id': self.id}
