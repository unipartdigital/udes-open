# -*- coding: utf-8 -*-

from collections import OrderedDict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from ..common import check_many2one_validity
from . import common


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    priority = fields.Selection(selection=common.PRIORITIES)

    # compute previous and next pickings
    u_prev_picking_ids = fields.One2many(
        'stock.picking', string='Previous Pickings',
        compute='_compute_related_picking_ids',
        help='Previous pickings',
    )
    u_next_picking_ids = fields.One2many(
        'stock.picking', string='Next Pickings',
        compute='_compute_related_picking_ids',
        help='Next pickings',
    )

    u_created_back_orders = fields.One2many(
        'stock.picking', string='Created Back Orders',
        compute='_compute_related_picking_ids',
        help='Created Back Orders',
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
    u_pending = fields.Boolean(compute='_compute_pending')

    # override batch_id to be copied
    batch_id = fields.Many2one(
        'stock.picking.batch', copy=True)

    u_quantity_done = fields.Float(
        'Quantity done', compute='_compute_picking_quantities',
        digits=(0, 0), store=False,
        help='Quantity done of the moves related to the picking')

    u_total_quantity = fields.Float(
        'Total quantity', compute='_compute_picking_quantities',
        digits=(0, 0), store=False,
        help='Total quantity todo of the moves related to the picking')

    u_has_discrepancies = fields.Boolean(
        string='Has discrepancies', compute='_compute_picking_quantities',
        readonly=True, help='Flag to indicate if the picking still has discrepancies.',
        )

    u_num_pallets = fields.Integer(
        'Total Pallets count', compute='_compute_picking_packages', store=False,
        help='Total number of different pallets in the picking')

    @api.depends('move_lines',
                 'move_lines.quantity_done',
                 'move_lines.ordered_qty')
    @api.one
    def _compute_picking_quantities(self):
        """ Compute the quantity done and to do of the picking from the moves """
        total_qty_done = 0.0
        total_qty_todo = 0.0
        has_discrepancies = False
        for move in self.move_lines:
            qty_done = move.quantity_done
            qty_todo = move.ordered_qty
            if qty_done != qty_todo:
                has_discrepancies = True
            total_qty_done += qty_done
            total_qty_todo += qty_todo

        self.u_quantity_done = total_qty_done
        self.u_total_quantity = total_qty_todo
        self.u_has_discrepancies = has_discrepancies

    @api.depends('move_line_ids',
                 'move_line_ids.result_package_id')
    @api.one
    def _compute_picking_packages(self):
        """ Compute the number of pallets from the operations """
        self.u_num_pallets = len(self.move_line_ids.mapped('result_package_id'))

    # Calculate previous/next pickings
    @api.depends('move_lines',
                 'move_lines.move_orig_ids',
                 'move_lines.move_dest_ids',
                 'move_lines.move_orig_ids.picking_id',
                 'move_lines.move_dest_ids.picking_id')
    def _compute_related_picking_ids(self):
        Picking = self.env['stock.picking']
        for picking in self:
            if picking.id:
                picking.u_created_back_orders = Picking.get_pickings(backorder_id=picking.id)

            picking.u_prev_picking_ids = picking.mapped(
                'move_lines.move_orig_ids.picking_id'
            )
            picking.u_next_picking_ids = picking.mapped(
                'move_lines.move_dest_ids.picking_id'
            )

    def can_handle_partials(self):
        self.ensure_one()
        return True

    def _compute_pending(self):
        ''' Compute if a picking is pending.
        Pending means it has previous pickings that are not yet completed.
        Skip the calculation if the picking type is allowed to handle partials.
        '''
        for picking in self:
            if picking.can_handle_partials() is False:
                prev_pickings_states = picking.u_prev_picking_ids.mapped('state')
                picking.u_pending = 'waiting' in prev_pickings_states or \
                                    'assigned' in prev_pickings_states
            else:
                picking.u_pending = False

    def assert_not_pending(self):
        for picking in self:
            if picking.can_handle_partials() is False \
                    and picking.u_pending is True:
                raise UserError(
                    _("Cannot validate %s until all of its"
                      " preceding pickings are done.") % picking.name)

    def action_done(self):
        """ Ensure we don't incorrectly validate pending pickings."""
        self.assert_not_pending()
        return super(StockPicking, self).action_done()

    def button_validate(self):
        """ Ensure we don't incorrectly validate pending pickings."""
        self.assert_not_pending()
        return super(StockPicking, self).button_validate()

    def assert_valid_state(self):
        """ Checks if the transfer is in a valid state, i.e., not done or cancel
            otherwise it raises and error
        """
        self.ensure_one()
        if self.state in ['done', 'cancel']:
            raise ValidationError(_('Wrong state of picking %s') % self.state)

    def add_unexpected_parts(self, product_quantities):
        """ By default allow to overreceive and it will be extended in
            a module where the picking type has a flag to decide this.
        """
        self.ensure_one()
        old_move_lines = self.move_line_ids
        self._create_moves(product_quantities, confirm=True, assign=True, unexpected=True)
        new_move_lines = (self.move_line_ids - old_move_lines)

        for ml in old_move_lines:
            if ml.qty_done > 0 and ml.product_uom_qty > ml.qty_done:
                # Note: when adding extra moves/move_lines, odoo will merge
                # them into one of the existing ones, therefore we need
                # to split the old_move_lines that have qty_done > 0 and
                # qty_done < product_uom_qty

                # TODO: handle this properly at odoo core:
                #       avoid to merge new move lines if qty_done > 0?

                # new_ml has qty_done 0 and ml is done

                new_ml = ml._split()
                new_move_lines |= new_ml
        # These are unexpected so the ordered_qty should be
        new_move_lines.write({"ordered_qty": 0})

        return new_move_lines

    def _create_moves_from_quants(self, quant_ids, **kwargs):
        """ Check that the quants are valid to be used in self and
            create moves calling _create_moves().
        """
        Quant = self.env['stock.quant']

        allow_partial = self.env.context.get('allow_partial')

        self.assert_valid_state()

        if isinstance(quant_ids, list):
            quants = Quant.browse(quant_ids)
        elif isinstance(quant_ids, type(Quant)):
            quants = quant_ids
        else:
            raise ValidationError(_('Wrong quant identifiers %s') % type(quant_ids))
        if not allow_partial:
            quants.assert_not_reserved()
            quants.assert_entire_packages()
        quants.assert_valid_location(self.location_id.id)

        # Call _create_moves() with context variable quants_ids in order
        # to filter the quants that stock.quant._gather returns
        self.with_context(quant_ids=quant_ids)._create_moves(
            quants.group_quantity_by_product(only_available=allow_partial), **kwargs)

    def _create_moves(self, products_info, values=None,
                      confirm=False, assign=False,
                      result_package=None, unexpected=False):
        """ Creates moves from products_info and adds it to the picking
            in self. Where products_info is a dictionary mapped by
            product ids and the value are the quantities.

            The picking is also confirmed/assigned if the flags are set to True.
            If result_package is set, it will update the result_package_id of the
            new move_lines when assign flag is True.
        """
        Product = self.env['product.product']
        Move = self.env['stock.move']
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

        for product_id, qty in products_info.items():
            move_vals = {
                'name': '{} {}'.format(qty, Product.browse(product_id).display_name),
                'product_id': product_id,
                'product_uom_qty': qty,
            }
            move_vals.update(values)
            move = Move.create(move_vals)
            if unexpected:
                move.ordered_qty = 0

        if confirm:
            # Use picking.action_confirm, which will merge moves of the same
            # product. In case that is not wanted use moves._action_confirm(merge=False)
            self.action_confirm()

        if assign:
            old_move_line_ids = self.move_line_ids
            # Use picking.action_assign or moves._action_assign to create move lines
            # with context variable bypass_reservation_update in order to avoid
            # to execute code specific for Odoo UI at stock.move.line.write()
            self.with_context(bypass_reservation_update=True).action_assign()
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
            origin=None,
            group_id=None,
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
            @param (optional) origin: string
                Value of the source document of the new picking
            @param (optional) group_id: int
                ID of the group where the stock is being assigned to

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
        if origin:
            values['origin'] = origin
        if group_id is not None:
            values['group_id'] = group_id
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
            # picking.move_line_ids.mapped('result_package_id').write({'package_id': False})
            pass

        return picking

    def update_picking(
            self,
            quant_ids=None,
            force_validate=False,
            validate=False,
            create_backorder=False,
            location_dest_id=None,
            location_dest_name=None,
            location_dest_barcode=None,
            result_package_name=None,
            package_name=None,
            move_parent_package=False,
            product_ids=None,
            picking_info=None,
            validate_real_time=False,
            location_id=None,
    ):
        """ Update/mutate the stock picking in self

            @param quant_ids: Array (int)
                An array of the quants ID to add to the stock.picking
            @param (optional) force_validate: Boolean
                Forces the transfer to be completed. Depends on parameters
            @param (optional) validate: Boolean
                Validate the transfer unless there are move lines todo, in
                that case it will raise an error.
            @param (optional) create_backorder: Boolean
                When true, allows to validate a transfer with move lines todo
                by creating a backorder.
            @param (optional) location_dest_id: int
                ID of the location where the stock is going to be moved to
            @param (optional) location_dest_name: string
                Name of the location where the stock is going to be moved to
            @param (optional) location_dest_barcode: string
                barcode of the location where the stock is going to be moved to
            @param (optional) result_package_name: string
                If it corresponds to an existing package/pallet that is not
                in an other location, we will set it to the `result_package_id`
                of the operations of the picking (i.e. transfer)
            @param (optional) move_parent_package: Boolean
                Used in pallets/nested packages, to maintain the move of the entire pallet.
                Defaults to False
            @param package_name: string
                Name of the package of the picking to be marked as done
            @param product_ids: Array of dictionaries
                An array with the products information to be marked as done,
                where each dictionary contains: barcode, qty and
                lot numbers if needed
            @param picking_info: dictionary
                Generic picking information to update the stock picking with
            @param (optional) validate_real_time: Boolean
                Used to specify if the update should be should be processed
                imidately or on confirmation of the picking.
            @param (optional) location_id: int
                Used when validating products from a location.
        """
        Location = self.env['stock.location']
        Package = self.env['stock.quant.package']
        self.assert_valid_state()

        values = {}

        # Updates stock picking with generic picking info
        if picking_info:
            self.write(picking_info)

        if quant_ids:
            # Create extra stock.moves to the picking
            self._create_moves_from_quants(quant_ids, confirm=True, assign=True,
                                           result_package=result_package_name)
            # when adding only do this?
            return True

        if location_dest_id or location_dest_barcode or location_dest_name:
            values['location_dest'] = location_dest_id or location_dest_barcode or location_dest_name
        if result_package_name:
            values['result_package'] = result_package_name
        if not move_parent_package:
            # not needed yet, move it outside udes_core
            # when false remove parent_id of the result_package_id ??
            # picking.move_line_ids.mapped('result_package_id').write({'package_id': False})
            pass

        # get all the stock.move.lines
        move_lines = self.move_line_ids

        if package_name:
            # a package is being marked as done
            values['package'] = package_name
            package = Package.get_package(package_name)
            move_lines = move_lines.get_package_move_lines(package)
            if not product_ids:
                # a full package is being validated
                # check if all parts have been reserved
                package.assert_reserved_full_package(move_lines)

        if product_ids:
            values['product_ids'] = product_ids
            # when updating products we migth want
            # to filter by location
            if location_id:
                location = Location.get_location(location_id)
                move_lines = move_lines.filtered(lambda ml: ml.location_id == location)

        picking = self
        if package_name or product_ids or force_validate:
            # mark_as_done the stock.move.lines
            mls_done = move_lines.mark_as_done(**values)

            if validate_real_time:
                picking = self._real_time_update(mls_done)
                validate = True

        if force_validate or validate:
            if picking.move_line_ids.get_lines_todo() and not create_backorder:
                raise ValidationError(
                    _('Cannot validate transfer because there'
                      ' are move lines todo'))
            # by default action_done will backorder the stock.move.lines todo
            # validate stock.picking
            picking.action_done()  # old do_transfer

    def _requires_backorder(self, mls):
        """ Checks if a backorder is required
            by checking if all move.lines
            within a picking is present in mls
        """
        mls_moves = mls.mapped('move_id')
        # return (mls_moves | self.move_lines) != mls_moves or \
        # (mls | self.move_line_ids) != mls or \
        # self.mapped('move_lines.move_orig_ids').filtered(lambda x: x.state not in ('done', 'cancel'))
        for move in self.move_lines:
            if move not in mls_moves or \
                    not move.move_line_ids == mls.filtered(lambda x: x.move_id == move) or \
                    move.move_orig_ids.filtered(lambda x: x.state not in ('done', 'cancel')):
                return True
        return False

    def _create_backorder(self, mls=None):
        """ Creates a backorder pick from self (expects a singleton)
            and a subset of stock.move.lines are then moved into it.
            The move from which the move lines have been transferred
            has the ordered_qty decrimented by the amount of the
            transftered lines.
        """
        Move = self.env['stock.move']
        # Based on back order creation in stock_move._action_done
        self.ensure_one()

        if mls is None:
            mls = self.move_line_ids.filtered(lambda x: x.qty_done > 0)

        # test that the intercetion of mls and move lines in picking
        # therefore we have some relevent move lines
        if not (mls & self.move_line_ids):
            raise ValidationError(_('There is no move lines within ' \
                                    'picking %s to backorder' % self.name))

        new_moves = Move.browse()

        for current_move in mls.mapped('move_id'):
            bk_move = Move.browse()
            current_mls = mls.filtered(lambda x: x.move_id == current_move)

            if current_mls == current_move.move_line_ids and \
                    not current_move.move_orig_ids.filtered(
                        lambda x: x.state not in ('done', 'cancel')):
                bk_move = current_move
            else:
                total_ordered_qty = sum(current_mls.mapped('ordered_qty'))
                total_initial_qty = sum(current_mls.mapped('product_uom_qty'))
                bk_move = current_move.copy({'picking_id': False,
                                             'move_line_ids': [],
                                             'move_orig_ids': [],
                                             'ordered_qty': total_ordered_qty,
                                             'product_uom_qty': total_initial_qty,
                                             })
                current_mls.write({'move_id': bk_move.id})
                current_move.with_context(bypass_reservation_update=True).write({
                    'ordered_qty': current_move.ordered_qty - total_ordered_qty,
                    'product_uom_qty': current_move.product_uom_qty - total_initial_qty,
                })

                if current_move.move_orig_ids:
                    (bk_move | current_move).update_orig_ids(current_move.move_orig_ids)

            new_moves |= bk_move

        # Create picking for completed move lines
        bk_picking = self.copy({
            'name': '/',
            'move_lines': [],
            'move_line_ids': [],
            'backorder_id': self.id,
        })
        new_moves.write({'picking_id': bk_picking.id, 'state': 'assigned'})
        new_moves.mapped('move_line_ids').write({'picking_id': bk_picking.id, 'state': 'assigned'})
        return bk_picking

    def _real_time_update(self, mls):
        """ Checks to see if the transfer of the move_lines would leave the
            stock.move empty if so it returns self else it returns a
            backorder comprising of the stock.move.lines provided
        """
        if not self._requires_backorder(mls):
            return self

        rt_picking = self._create_backorder(mls)
        return rt_picking

    def get_pickings(self,
                     origin=None,
                     package_name=None,
                     states=None,
                     picking_type_ids=None,
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

            @param (optional) package_name
                Search of stock.pickings associated with a specific
                package_name (exact match).

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

            @param (optional) picking_type_ids: Array (int)
                If it is set the pickings returned will be only from the picking types in the array.

            TODO: bulky
        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']
        Users = self.env['res.users']

        order = None

        if states is None:
            states = ['draft', 'cancel', 'waiting',
                      'confirmed', 'assigned', 'done']

        warehouse = Users.get_user_warehouse()
        if picking_type_ids is None:
            picking_type_ids = warehouse.get_picking_types().ids

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
        elif package_name:
            package = Package.get_package(package_name, no_results=True)
            if not package:
                return Picking.browse()
            domain = self._get_package_search_domain(package)
        elif picking_priorities:
            domain = [
                ('priority', 'in', picking_priorities),
                ('picking_type_id', '=', warehouse.pick_type_id.id),
                ('batch_id', '=', False),
            ]
            if picking_ids is not None:
                domain.append(('id', 'in', picking_ids))
            order = 'priority desc, scheduled_date, id'
            # TODO: add bulky field
            # if bulky is not None:
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
        # add the picking type ids to the domain
        domain.append(('picking_type_id', 'in', picking_type_ids))

        # add extra domain if there is any
        if extra_domain:
            domain.extend(extra_domain)

        pickings = Picking.search(domain, order=order)

        return pickings

    def _get_package_search_domain(self, package):
        """ Generate the domain for searching pickings of a package
        """
        return ['|', ('move_line_ids.package_id', '=', package.id),
                ('move_line_ids.result_package_id', '=', package.id)]

    def _prepare_info(self, priorities=None, fields_to_fetch=None):
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
            - u_pending: boolean (only if picking type does not handle partials)

            @param (optional) priorities
                Dictionary of priority_id:priority_name
        """
        self.ensure_one()

        if not priorities:
            priorities = OrderedDict(self._fields['priority'].selection)

        priority_name = priorities[self.priority]

        # @todo: (ale) move this out of the method as it's static code
        info = {"id": lambda p: p.id,
                "name": lambda p: p.name,
                "priority": lambda p: p.priority,
                "backorder_id": lambda p: p.backorder_id.id,
                "priority_name": lambda p: priority_name,
                "origin": lambda p: p.origin,
                "state": lambda p: p.state,
                "location_dest_id": lambda p: p.location_dest_id.id,
                "picking_type_id": lambda p: p.picking_type_id.id,
                "moves_lines": lambda p: p.move_lines.get_info()}

        # u_pending only included if we don't handle partials, otherwise field is irrelevant.
        if self.can_handle_partials() is False:
            info['u_pending'] = lambda p: p.u_pending

        if not fields_to_fetch:
            fields_to_fetch = info.keys()

        return {key: value(self) for key, value in info.items() if key in fields_to_fetch}

    def get_info(self, **kwargs):
        """ Return a list with the information of each picking in self.
        """
        # create a dict of priority_id:priority_name to avoid
        # to do it for each picking
        priorities = OrderedDict(self._fields['priority'].selection)
        res = []
        for picking in self:
            res.append(picking._prepare_info(priorities, **kwargs))

        return res

    @api.model
    def get_priorities(self):
        """ Return a list of dicts containing the priorities of the
            all defined priority groups, in the following format:
                [
                    {
                        'name': 'Picking',
                        'priorities': [
                            OrderedDict([('id', '2'), ('name', 'Urgent')]),
                            OrderedDict([('id', '1'), ('name', 'Normal')])
                        ]
                    },
                    {
                        ...
                    },
                    ...
                ]
        """
        return list(common.PRIORITY_GROUPS.values())

    @api.multi
    def get_move_lines_done(self):
        """ Return the recordset of move lines done. """
        move_lines = self.mapped('move_line_ids')

        return move_lines.filtered(lambda o: o.qty_done > 0)

    def is_valid_location_dest_id(self, location=None, location_ref=None):
        """ Whether the specified location or location reference
            (i.e. ID, name or barcode) is a valid putaway location
            for the picking.
            Expects a singleton instance.

            Returns a boolean indicating the validity check outcome.
        """
        Location = self.env['stock.location']
        self.ensure_one()
        assert location or location_ref, "Must specify a location or ref"
        dest_locations = None

        if location is not None:
            dest_locations = location
        else:
            dest_locations = Location.get_location(location_ref)

        if not dest_locations:
            raise ValidationError(_("The specified location is unknown."))

        valid_locations = Location.search(
            [('id', 'child_of', self.location_dest_id.id)])
        invalid_locations = dest_locations - valid_locations

        return len(invalid_locations) == 0

    @api.multi
    def open_stock_picking_form_view(self):
        self.ensure_one()
        view_id = self.env.ref('stock.view_picking_form').id
        return {
            'name': _('Internal Transfer'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.picking',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'res_id': self.id,
            'context': dict(self.env.context),
        }

    @api.multi
    def _refine_picking(self, text=None):
        """
        Unreserve the move lines of all pickings of the instance
        recordset.
        If the text argument is specified, it will be shown in the
        Odoo UI within each picking context.
        """
        for pick in self:
            if text:
                pick.message_post(body=text)

            pick.do_unreserve()
