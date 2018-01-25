# -*- coding: utf-8 -*-

from collections import OrderedDict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..common import check_many2one_validity

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # compute previous and next pickings
    u_prev_picking_ids = fields.One2many(
        'stock.picking', string='Previous Pickings',
        compute='_compute_prev_next_picking_ids',
        help='Previous pickings',
        )
    u_next_picking_ids = fields.One2many(
        'stock.picking', string='Next Pickings',
        compute='_compute_prev_next_picking_ids',
        help='Next pickings',
        )
    # search helpers for source and destination package
    u_package_id = fields.Many2one('stock.quant.package', 'Package',
                                   related='move_line_ids.package_id',
                                   help='Source package (used to search on pickings)',
                                   )
    u_result_package_id = fields.Many2one('stock.quant.package', 'Result Package',
                                   related='move_line_ids.result_package_id',
                                   help='Destination package (used to search on pickings)',
                                   )


    # Calculate previous/next pickings
    @api.depends('move_lines',
                 'move_lines.move_orig_ids',
                 'move_lines.move_dest_ids',
                 'move_lines.move_orig_ids.picking_id',
                 'move_lines.move_dest_ids.picking_id')
    def _compute_prev_next_picking_ids(self):
        for picking in self:
            picking.u_prev_picking_ids = picking.mapped(
                'move_lines.move_orig_ids.picking_id'
                )
            picking.u_next_picking_ids = picking.mapped(
                'move_lines.move_dest_ids.picking_id'
                )

    def assert_valid_state(self):
        """ Checks if the transfer is in a valid state, i.e., not done or cancel
            otherwise it raises and error
        """
        self.ensure_one()
        if self.state in ['done', 'cancel']:
            raise ValidationError(_('Wrong state of picking %s') % self.state)

    def add_unexpected_parts(self, product_quantities):
        """ TODO: unexpected parts, call picking._create_moves()
            if not overreceive raise error? check it inside overriding it?
            Test what happens when adding unexpected part of a serial numbered product

            By default allow overreceive, when overriding check it from the picking type
        """
        raise ValidationError(_('Not handling unexpected parts yet'))

    def _create_moves_from_quants(self, quant_ids, values=None,
                                  confirm=False, assign=False,
                                  result_package=None):
        """ Creates moves from quant_ids and adds it to the picking in self.
            The picking is also confirmed/assigned if the flags are set to True.
            If result_package is set, it will update the result_package_id of the
            new move_lines when assign flag is True.
        """
        # TODO: update it to create by quant_ids or dictionary of {product_id:qty}
        Product = self.env['product.product']
        Move = self.env['stock.move']
        Quant = self.env['stock.quant']
        Package = self.env['stock.quant.package']

        self.assert_valid_state()

        if values is None:
            values = {}
        values['picking_id'] = self.id
        if not 'location_id' in values:
            values['location_id'] = self.location_id.id
        if not 'location_dest_id' in values:
            values['location_dest_id'] = self.location_dest_id.id
        if not 'picking_type_id' in values:
            values['picking_type_id'] = self.picking_type_id.id
        if not 'product_uom' in values:
            default_uom_id = self.env.ref('product.product_uom_unit').id
            values['product_uom'] = default_uom_id

        if isinstance(quant_ids, list):
            quants = Quant.browse(quant_ids)
        elif isinstance(quant_ids, type(Quant)):
            quants = quant_ids
        else:
            raise ValiationError(_('Wrong quant identifiers %s') % type(quant_ids))
        quants.assert_not_reserved()
        quants.assert_entire_packages()
        quants.assert_valid_location(values['location_id'])

        for product_id, qty in quants.group_quantity_by_product().items():
            move_vals = {
                    'name': '{} {}'.format(qty, Product.browse(product_id).display_name),
                    'product_id': product_id,
                    'product_uom_qty': qty,
                }
            move_vals.update(values)
            move = Move.create(move_vals)

        if confirm:
            # Use picking.action_confirm, which will merge moves of the same
            # product. In case that is not wanted use moves._action_confirm(merge=False)
            self.action_confirm()

        if assign:
            old_move_line_ids = self.move_line_ids
            # Use picking.action_assign or moves._action_assign to create move lines
            # Context variables:
            # - quant_ids:
            #   filters the quants that stock.quant._gather returns
            # - bypass_reservation_update:
            #   avoids to execute code specific for Odoo UI at stock.move.line.write()
            self.with_context(quant_ids=quant_ids, bypass_reservation_update=True).action_assign()
            if result_package:
                # update result_package_id of the new move_line_ids
                package = Package.get_package(result_package)
                new_move_line_ids = self.move_line_ids - old_move_line_ids
                new_move_line_ids.write({'result_package_id': package.id})


    def create_picking(
            self,
            quant_ids,
            location_id,
            picking_type_id=None,
            location_dest_id=None,
            result_package_id=None,
            move_parent_package=False,
    ):
        """ Creates a stock.picking and stock.moves for a given list
            of stock.quant ids

            @param quant_ids: Array (int)
                An array of the quants ID to add to the stock.picking
            @param location_id: int
                ID of the location where the stock.picking is moving from.
            @param (optional) picking_type_id: int
                The type of the stock.picking.
            @param (optional) location_dest_id: int
                ID of the location where the stock is going to be moved to.
            @param (optional) result_package_id: int
                The target package ID
            @param (optional) move_parent_package: Boolean
                Used in pallets/nested packages, to maintain the move of the entire pallet.
                Defaults to False

        """
        Picking = self.env['stock.picking']
        PickingType = self.env['stock.picking.type']
        Location = self.env['stock.location']
        Users = self.env['res.users']

        # get picking_type from picking_type_id or internal transfer
        if picking_type_id:
            picking_type = PickingType.get_picking_type(picking_type_id)
        else:
            warehouse = Users.get_user_warehouse()
            picking_type = warehouse.int_type_id

        if not location_dest_id:
            location_dest_id = picking_type.default_location_dest_id.id

        # check params
        for (field, obj, id_) in [
            ('location_id', Location, location_id),
            ('location_dest_id', Location, location_dest_id),
        ]:
            check_many2one_validity(field, obj, id_)

        # Create stock.picking
        values = {
            'location_id': location_id,
            'location_dest_id': location_dest_id,
            'picking_type_id': picking_type.id,
        }
        picking = Picking.create(values.copy())

        # Create stock.moves
        picking._create_moves_from_quants(quant_ids, values=values.copy(),
                                          confirm=True, assign=True,
                                          result_package=result_package_id)

        # TODO: this might be in the package_hierarchy module, because odoo by default
        #       does not handle parent packages
        if not move_parent_package:
            # not needed yet
            # when false remove parent_id of the result_package_id ??
            #picking.move_line_ids.mapped('result_package_id').write({'package_id': False})
            pass

        return picking

    def update_picking(
            self,
            quant_ids=None,
            force_validate=False,
            location_dest_id=None,
            location_barcode=None,
            result_package_name=None,
            package_name=None,
            move_parent_package=False,
            products_info=None,
    ):
        """ Update/mutate the stock picking in self

            @param quant_ids: Array (int)
                An array of the quants ID to add to the stock.picking
            @param (optional) force_validate: Boolean
                Forces the transfer to be completed. Depends on parameters
            @param (optional) location_dest_id: int
                ID of the location where the stock is going to be moved to
            @param (optional) result_package_name: string
                If it corresponds to an existing package/pallet that is not
                in an other location, we will set it to the `result_package_id`
                of the operations of the picking (i.e. transfer)
            @param (optional) move_parent_package: Boolean
                Used in pallets/nested packages, to maintain the move of the entire pallet.
                Defaults to False
        """
        Location = self.env['stock.location']
        Package = self.env['stock.quant.package']

        self.assert_valid_state()

        values = {}

        if quant_ids:
            # Create extra stock.moves to the picking
            self._create_moves_from_quants(quant_ids, confirm=True, assign=True,
                                           result_package=result_package_name)
            # when adding only do this?
            return True

        if location_dest_id or location_barcode:
            values['location_dest'] = location_dest_id or location_barcode
        if result_package_name:
            values['result_package'] = result_package_name
        if not move_parent_package:
            # not needed yet, move it outside udes_core
            # when false remove parent_id of the result_package_id ??
            #picking.move_line_ids.mapped('result_package_id').write({'package_id': False})
            pass

        if package_name:
            values['package'] = package_name
        if products_info:
            values['products_info'] = products_info

        # get all the stock.move.lines
        move_lines = self.move_line_ids

        if package_name or products_info or force_validate:
            # validate stock.move.lines
            move_lines.validate(**values)

        # TODO: or validate?
        if force_validate:
            # validate stock.picking
            self.action_done() # old do_transfer

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
                     bulky=None,
                     extra_domain=None,
                     ):

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
                TODO: this needs to be in a new module and extend this function
                    for instance adding the extra criteria to extra_domain paramater

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
        # add extra domain if there is any
        if extra_domain:
            domain.extend(extra_domain)

        pickings = Picking.search(domain, order=order)

        return pickings

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
