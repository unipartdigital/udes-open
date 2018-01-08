from odoo import models, fields, _
from odoo.exceptions import ValidationError

from ..common import check_many2one_validity, group_qty_by_product


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    def create_picking(
            self,
            quant_ids,
            location_id,
            picking_type_id=None,
            location_dest_id=None,
            result_package_id=None,
            move_parent_package=False,
            **kwargs
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
        Move = self.env['stock.move']
        Product = self.env['product.product']
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

        # check params
        for (field, obj, id_) in [
            ('location_id', Location, location_id),
            ('location_dest_id', Location, location_dest_id),
        ]:
            check_many2one_validity(field, obj, id_)

        quants = Quant.browse(quant_ids)
        quants.ensure_not_reserved()
        quants.ensure_entire_packages()

        # Create stock.picking
        vals = {
            'picking_type_id': picking_type.id,
            'location_dest_id': location_dest_id,
            'location_id': location_id,
        }
        vals.update(kwargs)
        picking = Picking.create(vals)

        # create stock moves
        # TODO: create function to create moves from quants + call action_assign and action_confirm?
        # TODO: create a function at quants that returns the group ?
        # TODO: get all the display_names with one call to DB?
        for product_id, qty in group_qty_by_product(quants).items():
            move_vals = {
                    'name': '{} {}'.format(qty, Product.browse(product_id).display_name),
                    'product_id': product_id,
                    'product_uom_qty': qty,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'product_uom': default_uom_id,
                    'picking_id': picking.id,
                }
            move = Move.create(move_vals)

        # Use picking.action_cofirm or moves._action_confirm()
        picking.action_confirm()

        # Use picking.action_assign or moves._action_assign to create move lines
        # Context variables:
        # - quant_ids:
        #   filters the quants that stock.quant._gather returns
        # - bypass_reservation_update:
        #   avoids to execute code specific for Odoo UI at stock.move.line.write()
        picking.with_context(quant_ids=quant_ids, bypass_reservation_update=True).action_assign()

        if result_package_id:
            picking.move_line_ids.write({'result_package_id': result_package_id})
        # TODO: this might be in the package_hierarchy module, because odoo by default
        #       does not handle parent packages
        if not move_parent_package:
            # when false remove parent_id of the result_package_id ??
            #picking.move_line_ids.mapped('result_package_id').write({'package_id': False})
            pass

        return picking
