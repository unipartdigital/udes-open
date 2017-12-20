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
            package = Package.get_package(package_barcode)
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


    def hook_for_check_before_create_picking(self, quants, *args, **kwargs):
        """
        Override this method in projects if more checks are needed on quants
        :return: None
        :raise: ValidationError if one of the checks do not pass
        """
        #TODO: implement at blocked module. similar to stock.picking._check_locations_not_blocked
        #quants._check_location_not_blocked()
        pass

    def create_picking(
            self,
            quant_ids,
            location_id,
            location_dest_id=None,
            picking_location_dest_id=None,
            picking_id=None,
            result_package_id=None,
            track_parent_package=False,
            force_unreserve=False,
            linked=False,
            picking_type_id=False,
            force_picking_dest_id=False,
            group_id=False,
            **kwargs
    ):
        """
        # TODO: update description

        """
        Picking = self.env['stock.picking']
        PickingType = self.env['stock.picking.type']
        Move = self.env['stock.move']
        Product = self.env['product.product']
        MoveLine = self.env['stock.move.line']
        Quant = self.env['stock.quant']
        Location = self.env['stock.location']
        Users = self.env['res.users']

        if picking_type_id:
            picking_type = PickingType.browse(picking_type_id)
        else:
            warehouse = Users.get_user_warehouse()
            picking_type = warehouse.int_type_id

        default_uom_id = self.env.ref('product.product_uom_unit').id

        if not location_dest_id:
            location_dest_id = picking_type.default_location_dest_id.id
        if not picking_location_dest_id:
            picking_location_dest_id = picking_type.default_location_dest_id.id

        quants = Quant.search([('id', 'in', quant_ids)])
        if linked:
            # NOT NEEDED FOR STOCK MOVE
            # quants should be unreserved from current moves
            # TODO: since quants are not related to moves anymore
            #       probably we don't have to unreserve the quants, only
            #       duplicate the moves
            force_unreserve = True
            # get moves linking info
            # TODO: create function to get moves related to quants
            #current_moves = quants.mapped('reservation_id')
            # TODO: implement function to get the following info
            current_moves_info = dict()
            for move in current_moves:
                current_moves_info[move.id] = {
                        'move_orig_ids': move.move_orig_ids,
                        'move_dest_id': move.move_dest_id,
                        # TODO: not needed?
                        #'reserved_quant_ids': move.reserved_quant_ids,
                    } 
            # destination location = origin location of current picking
            location_dest_id = current_moves.mapped('picking_id.location_id').id
            picking_location_dest_id = location_dest_id

        if force_unreserve:
            # NOT NEEDED FOR STOCK MOVE
            # TODO: migrate
            #quants.force_unreserve()
            pass

        # TODO: implement
        #quants.check_reserved()
        # TODO: implement
        #quant.check_partial_packages()
        self.hook_for_check_before_create_picking(quants)


        # TODO: use a function to get or create picking
        # TODO: get values from the created picking
        if picking_id:
            # transfer exists
            new_transfer = Picking.browse(picking_id)
            if new_transfer.state in ('cancel', 'done'):
                raise ValidationError(
                    _('The picking {} cannot be in the state {}'.format(
                        new_transfer.name, new_transfer.state)))
            # reuse the group of the transfer
            group_id = new_transfer.group_id.id
        else:
            # transfer needs to be created
            vals = {
                'picking_type_id': picking_type.id,
                'location_dest_id': picking_location_dest_id,
                'location_id': location_id,
                'group_id': group_id,
            }
            vals.update(kwargs)
            new_transfer = Picking.create(vals)


        # when not linked, moves are created from quants info
        # when linked, moves are created from current quants moves info
        created_moves = Move.browse()
        if not linked:
            # TODO: function to create moves and move.lines from groups of quants
            # TODO: use groupby to group instead of a function
            # TODO: group quants by key: product only?
            # create stock move
            move_vals = [
                {
                    'name': '{} {}'.format(qty, Product.browse(product_id).display_name),
                    'product_id': product_id,
                    'product_uom_qty': qty,
                    'location_id': location_id,
                    'location_dest_id': picking_location_dest_id,
                    'product_uom': default_uom_id,
                    'picking_id': new_transfer.id,
                    'group_id': group_id,
                }
                for product_id, qty in group_qty_by_product(quants).items()
            ]
            for move_val in move_vals:
                move = Move.create(move_val)
                created_moves += move
                # "reserve" each quant with the same product as the move
                # to the move through the "reservation_id" field
                # TODO: reserve now is set reserved_quantity = quantity
                #quants.filtered(
                #    lambda q: q.product_id.id == move_val['product_id']
                #).write({'reservation_id': move.id})
        else:
            for move in current_moves:
                new_move = move.copy({
                        'picking_id': new_transfer.id,
                        'picking_type_id': picking_type.id,
                        'location_id': location_id,
                        'location_dest_id': location_id,
                        # point new move to current move
                        # TODO: this is a many2many relation now
                        #'move_dest_id': move.id,
                        'group_id': group_id or move.group_id.id,
                    })
                created_moves += new_move
                # point previous moves to new move
                # TODO: this is now a many2many relation
                #current_moves_info[move.id]['move_orig_ids'].write({'move_dest_id': new_move.id})
                # assign quants to new move
                # TODO: reserve now is set reserved_quantity = quantity
                #       probably we don't unreserve
                #current_moves_info[move.id]['reserved_quant_ids'].write({'reservation_id': new_move.id})

        # call action_confirm:
        # - chain of moves will be created if needed
        # - procurement group will be created if needed
        # TODO: migrate picking_type.u_create_group and extend action_confirm
        #       probably not needed for stock move
        new_transfer.action_confirm()
        # set the stock moves as assigned since they still have reserved_quant_ids
        created_moves.write({'state': 'assigned'})


        # TODO: group quants by key: product, location, lot, package
        # TODO: create one move.line per group and relate it to a move (similar to step #2)

        # TODO: since now move.lines are related to moves, probably we can create moves and
        #       move lines at the same time, so the following code should be inside create
        #       moves
        """
        # 1) create one operation per package_id in quants (corresponding to quant_ids)
        #   future improvement: one operation per parent package if we have all the
        #   packages of the parent package (e.g. pallet) in the transfer
        #   where parent_package (e.g. pallet) = package_id.parent_id
        packages = quants.mapped('package_id')
        for pack in packages:
            op_vals = {
                'package_id': pack.id,
                'picking_id': new_transfer.id,
                'location_id': pack.location_id.id,
                'location_dest_id': location_dest_id,
                'product_qty': 1,
            }
            # if the package is in a parent_package e.g. pallet (pack_id.parent_id is set)
            # we have to set the result_package_id, otherwise we will lose
            # the parent package (e.g. pallet) info.
            if result_package_id:
                op_vals['result_package_id'] = result_package_id
            elif track_parent_package and pack.parent_id:
                op_vals['result_package_id'] = pack.parent_id.id
            Operation.create(op_vals)
        # 2) create one operation for each product without packages per location
        quants_without_package = quants.filtered(lambda x: not x.package_id)
        by_prod_loc = lambda x: (x.product_id.id, x.location_id.id)
        quants_by_prod_loc = {(Product.browse(prod), Location.browse(loc)): Quant.union(*qs)
                                for (prod, loc), qs
                                in groupby(quants_without_package.sorted(key=by_prod_loc), key=by_prod_loc)}
        for (prod, loc), prod_quants in quants_by_prod_loc.iteritems():
            qty = prod_quants.total_qty()
            op_vals = {
                'picking_id': new_transfer.id,
                'location_id': loc.id,
                'location_dest_id': location_dest_id,
                'product_id': prod.id,
                'product_uom_id': default_uom_id,
                'product_qty': qty,
            }
            # case where we are moving quants from A to B and they have to be in a package in location B
            if result_package_id:
                op_vals['result_package_id'] = result_package_id
            Operation.create(op_vals)
        """
        # recompute quantities, to recompute the links (stock.move.operation.link)
        # TODO: not needed anymore, check if we need something similar
        #new_transfer.do_recompute_remaining_quantities()
        # make the new_transfer available
        new_transfer.state = 'assigned'
        if force_picking_dest_id:
            new_transfer.location_dest_id = location_dest_id

        return new_transfer
