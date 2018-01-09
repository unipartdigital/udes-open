# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

from ..common import check_many2one_validity


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def ensure_valid_state(self):
        """ Checks if the transfer is in a valid state, i.e., not done or cancel
        """
        self.ensure_one()
        if self.state in ['done', 'cancel']:
            raise ValidationError(_('Wrong state of picking %s') % self.state)

    def _create_moves_from_quants(self, quant_ids, values=None, confirm=False, assign=False):
        """ Creates moves from quant_ids and adds it to the picking in self.
        """
        # TODO: update it to create by quant_ids or dictionary of {product_id:qty}
        Product = self.env['product.product']
        Move = self.env['stock.move']
        Quant = self.env['stock.quant']

        self.ensure_valid_state()

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
        # TODO: change ensure for assert
        quants.ensure_not_reserved()
        quants.ensure_entire_packages()
        quants.ensure_valid_location(values['location_id'])

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
            # Use picking.action_assign or moves._action_assign to create move lines
            # Context variables:
            # - quant_ids:
            #   filters the quants that stock.quant._gather returns
            # - bypass_reservation_update:
            #   avoids to execute code specific for Odoo UI at stock.move.line.write()
            self.with_context(quant_ids=quant_ids, bypass_reservation_update=True).action_assign()


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
            # TODO: create function
            picking_type = PickingType.browse(picking_type_id)
            if not picking_type.exists():
                raise ValidationError(
                        _('Cannot find picking type with id %s') %
                        picking_type_id)
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
        picking._create_moves_from_quants(quant_ids, values=values.copy(), confirm=True, assign=True)

        # TODO: move it inside create_moves?
        if result_package_id:
            picking.move_line_ids.write({'result_package_id': result_package_id})
        # TODO: this might be in the package_hierarchy module, because odoo by default
        #       does not handle parent packages
        if not move_parent_package:
            # not needed yet
            # when false remove parent_id of the result_package_id ??
            #picking.move_line_ids.mapped('result_package_id').write({'package_id': False})
            pass

        return picking

    @api.multi
    def update_picking(
            self,
            quant_ids=None,
            force_validate=False,
            location_dest_id=None,
            result_package_barcode=None,
            move_parent_package=False,
    ):
        """ Update/mutate the stock picking in self

            @param quant_ids: Array (int)
                An array of the quants ID to add to the stock.picking
            @param (optional) force_validate: Boolean
                Forces the transfer to be completed. Depends on parameters
            @param (optional) location_dest_id: int
                ID of the location where the stock is going to be moved to
            @param (optional) result_package_barcode: string
                If it corresponds to an existing package/pallet that is not
                in an other location, we will set it to the `result_package_id`
                of the operations of the picking (i.e. transfer)
            @param (optional) move_parent_package: Boolean
                Used in pallets/nested packages, to maintain the move of the entire pallet.
                Defaults to False
        """
        Location = self.env['stock.location']
        Package = self.env['stock.quant.package']

        self.ensure_valid_state()

        values = {}

        if quant_ids:
            # Create stock.moves
            self._create_moves_from_quants(quant_ids, confirm=True, assign=True)

        if location_dest_id:
            values['location_dest_id'] = location_dest_id
        if result_package_barcode:
            # not needed for now, this was used to move packages inside pallets?
            #values['result_package_barcode'] = result_package_barcode
            pass
        if not move_parent_package:
            # not needed yet
            # when false remove parent_id of the result_package_id ??
            #picking.move_line_ids.mapped('result_package_id').write({'package_id': False})
            pass

        if force_validate:
            # get all the stock.move.lines
            move_lines = self.move_line_ids
            # validate stock.move.lines
            move_lines.validate(**values)
            # validate stock.picking
            self.action_done() # old do_transfer
