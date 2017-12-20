# -*- coding: utf-8 -*-

from collections import OrderedDict

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = "stock.picking"


    @api.multi 
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

        """ TODO: add docstring
            TODO: bulky
            TODO: handle move lines
        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']
        Users = self.env['res.users']

        pickings = Picking.browse()
        domain = []
        order = None

        if states is None:
            states = ['draft', 'cancel', 'waiting',
                      'confirmed', 'assigned', 'done']
        if self:
            domain = [('id', 'in', self.mapped('id'))]
        elif origin:
            domain = [('origin', '=', origin)]
        elif backorder_id:
            domain = [('backorder_id', '=', backorder_id)]
        elif result_package_id:
            domain = [('move_line_ids.result_package_id', '=', result_package_id)]
        elif product_id:
            if not location_id:
                raise ValidationError(_("Please supply a location_id"))
            domain = [
                ('move_line_ids.product_id', '=', product_id),
                ('move_line_ids.location_id', '=', location_id)
            ]
        elif package_barcode:
            package = Package.search([('name', '=', package_barcode)])
            # TODO: change = to child_of when we add package hierachy ?
            domain = ['|', ('move_line_ids.package_id', '=', package.id),
                           ('move_line_ids.result_package_id', '=', package.id)]
            # TODO: instead of using this variable we can use a context variable
            #list_data_filters['stock_pack_operations'] = {'self': {'package_id': pallet.id}}
            #if allops:
            #    list_data_filters['stock_pack_operations']['allops'] = True
        elif picking_priorities:
            warehouse = Users.get_user_warehouse()
            domain = [
                ('priority', 'in', picking_priorities),
                ('picking_type_id', '=', warehouse.pick_type_id.id),
                ('batch_id', '=', False),
            ]
            if picking_ids is not None:
                domain.append(('id', 'in', picking_ids))
            order='priority desc, scheduled_date, id'
            # TODO: add bulky field
            #if bulky is not None:
            #    pickings = pickings.filtered(lambda p: p.u_contains_bulky == bulky)
        elif picking_ids:
            domain = [('id', 'in', picking_ids)]
        elif location_id:
            warehouse = Users.get_user_warehouse()
            domain = [
                ('location_id', '=', location_id),
                ('picking_type_id', '=', warehouse.int_type_id.id)
            ]
        else:
            raise ValidationError(_('No valid options provided.'))

        # add the states to the domain
        domain.append(('state', 'in', states))

        if domain:
            pickings = Picking.search(domain, order=order)

        return pickings

    @api.multi
    def _prepare_info(self, priorities):
        """ TODO: add docstring
        id  int     
        name    string  
        priority    int     
        backorder_id    int     If this shipment is split, this refers to the stock.picking that has already been processed. For example, if we are expecting 10 items in stock.picking 1, but only process 6 then try to validate the stock.picking, we will be asked to create a backorder of the remaining 4 in the picking (stock.picking.id = 1), the new picking (i.e. stock.picking.id = 2) with have backorder_id = 1, to refer to the previous 6 that were processed.
        priority_name   string  Computed field, used by the API.
        origin  string  Typically used as a text reference of where the stock.picking came from. During goods in, this is the ASN (advanced ship notice - the supplier's delivery reference)
        location_dest_id    int     ID of the stock.location where the stock needs to move to
        picking_type_id     int     See below
        """
        self.ensure_one()
        priority_name = priorities[self.priority]

        return {"id": self.id,
                "name": self.name,
                "priority": self.priority,
                "backorder_id": self.backorder_id.id,
                "priority_name": priority_name,
                "origin": self.origin,
                "location_dest_id": self.location_dest_id.id,
                "picking_type_id": self.picking_type_id.id,
                "moves_lines": self.move_lines.get_info()
               }

    @api.multi
    def get_info(self):
        """ TODO: add docstring
        """
        priorities = OrderedDict(self._fields['priority'].selection)
        res = []
        for picking in self:
            res.append(picking._prepare_info(priorities))

        return res
