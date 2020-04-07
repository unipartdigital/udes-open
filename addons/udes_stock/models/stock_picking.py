# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sequence = fields.Integer(
        'Sequence', default=0, help="Used to order the 'All Operations' kanban view"
    )

    def get_empty_locations(self):
        """ Returns the recordset of locations that are child of the
            instance dest location and are empty.
            Expects a singleton instance.
        """
        return self._get_child_dest_locations(aux_domain=[('barcode', '!=', False), ('quant_ids', '=', False)])

    def _get_child_dest_locations(self, aux_domain=None):
        """ Return the child locations of the instance dest location.
            Extra domains are added to the child locations search query,
            when specified.
            Expects a singleton instance.
        """
        Location = self.env['stock.location']

        domain = [('id', 'child_of', self.location_dest_id.ids)]
        if aux_domain is not None:
            domain.extend(aux_domain)
        return Location.search(domain)

    def get_move_lines(self, done=None):
        """ Get move lines associated to picking, uses functions in stock_move_line
            :kwargs:
                - done: Boolean
                    When not set means to return all move lines of the picking.
                    Flag, if true returns all done move lines, else returns all incomplete
                    move lines associated to picking
            :returns: Move lines of picking
        """
        mls = self.move_line_ids
        if done:
            return self.move_line_ids.get_lines_done()
        elif done == False:
            return self.move_line_ids.get_lines_incomplete()
        return mls

    def _backorder_move_lines(self, mls=None):
        """ Creates a backorder pick from self (expects a singleton)
            and a subset of stock.move.lines are then moved into it.

            Ensure this function is only called if _requires_back_order is True
            if everything is done - then a new pick is created and the old one is empty
        """
        Move = self.env['stock.move']
        # Based on back order creation in stock_move._action_done
        self.ensure_one()

        if mls is None:
            mls = self.move_line_ids.filtered(lambda x: x.qty_done > 0)

        # Test that the intersection of mls and move lines in picking is empty,
        # therefore we have some relevant move lines
        if not (mls & self.move_line_ids):
            raise ValidationError(
                _('There are no move lines within picking %s to backorder') % self.name
            )

        new_moves = Move.browse()
        for move, move_mls in mls.groupby('move_id'):
            new_moves |= move.split_out_move_lines(move_mls)

        # Create picking for completed move
        bk_picking = self.copy({'name': '/', 'move_lines': [(6, 0, new_moves.ids)], 'move_line_ids': [(6, 0, new_moves.move_line_ids.ids)], 'backorder_id': self.id})

        return bk_picking

    def _requires_backorder(self, mls):
        """ Checks if a backorder is required by checking if all move lines
            within a picking are present in mls
            Cannot be consolidated with _check_backorder in Odoo core, because it
            does not take into account any move lines parameter.
        """
        mls_moves = mls.move_id
        for move in self.move_lines:
            if (
                move not in mls_moves
                or not move.move_line_ids == mls.filtered(lambda x: x.move_id == move)
                or move.move_orig_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            ):
                return True
        return False

    def create_picking(
        self,
        picking_type,
        products_info=None,
        confirm=False,
        assign=False,
        create_batch=False,
        **kwargs,
    ):
        """ Create and return a picking for the given picking_type
            For multiple pickings a list of lists of dicts of product_info should be passed, 
            and pickings with the same picking_type and other kwargs are the same. 
            The kwargs are applied to pickings, not moves. If needed, the moves can be created outside of create_pickings with _create_moves
            
            
            :args:
                - picking_type: picking type of the picking
            :kwargs:
                - products_info: list of dicts (or list(list(dicts)) for multiple picks) with product information
                - confirm: boolean flag to trigger action_confirm
                - assign: boolean flag to trigger action_assign
                - create_batch: boolean flag if a batch should be created

        """
        Picking = self.env['stock.picking']

        # Prepare stock.picking info
        picking_values, products_info = self._prepare_picking_info(picking_type, products_info=products_info, **kwargs)
        # Create pickings
        pickings = Picking.create(picking_values)
        # Prepare stock.moves
        if products_info:
            move_values = self._prepare_move(pickings, products_info)
            # Create stock.moves
            self._create_move(move_values)
            
        if confirm:
            pickings.action_confirm()

        if assign:
            pickings.action_assign()

        if create_batch:
            self._create_batch(pickings)
        return pickings

    def _prepare_picking_info(self, picking_type, products_info=None, **kwargs):
        """ Prepare the picking_info and products_info
        :args:
            - picking_type: picking type of the picking
        
        :kwargs:
            - products_info: None or list of dicts with product information
        
        :returns:
            picking_values: list(dict) of picking values
            products_info: None if products_info is None, or list(list(dict)) of product, qty info
        """
        picking_values = {
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
        }
        picking_values.update(kwargs)
        if not products_info:
            return [picking_values], products_info
        else:
            if any(isinstance(el, list) for el in products_info):
                num_pickings = len(products_info)
                picking_vals = [picking_values.copy() for i in range(num_pickings)]
            else:
                # Convert picking values to a list of picking values
                picking_vals = [picking_values]
                # Convert the products_info to a list of lists
                products_info = [products_info]
            return picking_vals, products_info


    def _create_batch(self, pickings):
        """ Create batch """
        PickingBatch = self.env['stock.picking.batch']
        PickingBatch.create({'picking_ids': [(6, 0, pickings.ids)]})

    def _prepare_move(self, pickings, products_info, **kwargs):
        """ Return a list of the move details to be used later in creation of the move(s).
            The purpose of this is to allow for multiple moves to be created at once.

            :args:
                - pickings: iterable of picking objects to be assigned to the moves
                - products_info: list(list(dict)) with dict of product and qty

            :returns:
                Move_values: list(dict)

        """
        move_values = []
        for i, picking in enumerate(pickings):
            for product_info in products_info[i]:
                product = product_info.get('product')
                qty = product_info.get('qty')
                vals = {
                    'product_id': product.id,
                    'name': product.name,
                    'product_uom': product.uom_id.id,
                    'product_uom_qty': qty,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'picking_id': picking.id,
                    'priority': picking.priority,
                    'picking_type_id': picking.picking_type_id.id,
                }
                vals.update(kwargs)
                move_values.append(vals)
        return move_values

    @api.model
    def _create_move(self, move_values):
        """ Create and return move(s) for the given move_values.
            Should be used in conjunction with _prepare_move to obtain move_values

            :args:
                - move_values: list of dictionary values (or single dictionary) to create move
            
            :returns:
                - move
        """
        Move = self.env['stock.move']
        return Move.create(move_values)
