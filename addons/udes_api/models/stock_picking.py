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

        """ Search for pickings by various criteria

            @param (optional) origin
                Search for stock.picking records based on the origin
                field. Needs to be a complete match.

            @param (optional) package_barcode
                Search of stock.pickings associated with a specific
                package_barcode (exact match).

            @param (optional) product_id
                If it is set then location_id must also be set and stock.pickings
                are found using both of those values (states is optional).

            @param (optional) location_id
                If it is set then only internal transfers acting on that
                location are considered. In all cases, if states is set
                then only pickings in those states are considered.

            @param (optional) backorder_id
                Id of the backorder picking. If present, pickings are found
                by backorder_id and states.

            (IGNORE FOR NOW) @param (optional) allops: Boolean.
                If True, all pack operations are included. If False, only
                pack operations that are for the pallet identified by param
                pallet (and it's sub-packages) are included.
                Defaults to True.

            @param (optional) states
                A List of strings that are states for pickings. If present
                only pickings in the states present in the list are
                returned.
                Defaults to all, possible values:
                'draft', 'cancel', 'waiting', 'confirmed', 'assigned', 'done'

            @param (optional) result_package_id
                If an id is supplied all pickings that are registered to
                this package id will be returned. This can also be used
                in conjunction with the states parameter

            @param (optional) picking_priorities
                When supplied all pickings of set priorities and states
                will be searched and returned

            @param (optional) picking_ids
                When supplied pickings of the supplied picking ids will
                be searched and returned. If used in conjunction with
                priorities then only those pickings of those ids will be
                returned.

            @param (optional) bulky: Boolean
                This is used in conjunction with the picking_priorities
                parameter to return pickings that have bulky items

            TODO: bulky
            TODO: handle move lines
        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']
        Users = self.env['res.users']

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
            #    domain.append(('u_contains_bulky', '=', bulky))
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

        pickings = Picking.search(domain, order=order)

        return pickings

    @api.multi
    def _prepare_info(self, priorities=None):
        """
            Prepares the following info of the picking in self:
            - id: int
            - name: string
            - priority: int
            - backorder_id: int
            - priority_name: string
            - origin: string
            - location_dest_id: int
            - picking_type_id: int
            - move_lines: [{stock.move}]

            @param (optional) priorities
                Dictionary of priority_id:priority_name
        """
        self.ensure_one()
        if not priorities:
            priorities = OrderedDict(self._fields['priority'].selection)
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
        """ Return a list with the information of each picking in self.
        """
        # create a dict of priority_id:priority_name to avoid
        # to do it for each picking
        priorities = OrderedDict(self._fields['priority'].selection)
        res = []
        for picking in self:
            res.append(picking._prepare_info(priorities))

        return res
