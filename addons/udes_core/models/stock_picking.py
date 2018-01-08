from odoo import models, fields, _
from odoo.exceptions import ValidationError

from ..common import check_many2one_validity, group_qty_by_product


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    def create_picking(
            self,
            quant_ids,
            location_id,
            location_dest_id=None,
            result_package_id=None,
            result_package_name=None,
            move_parent_package=False,
            picking_type_id=False,
            **kwargs
    ):
        """
            TODO
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

        # transfer needs to be created
        vals = {
            'picking_type_id': picking_type.id,
            'location_dest_id': location_dest_id,
            'location_id': location_id,
        }
        vals.update(kwargs)
        picking = Picking.create(vals)

        # create stock moves
        # TODO: create function to create moves from quants, action_assign and action_confirm?
        # TODO: create a function at quants that returns the group ?
        # TODO: get all the display_names with one call to DB?
        #created_moves = Move.browse()
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
            #created_moves |= move

        # call action_confirm:
        # - chain of moves will be created if needed
        # - procurement group will be created if needed (this needs u_create_group)
        # TODO: migrate picking_type.u_create_group and extend action_confirm
        #       probably not needed for stock move
        # TODO: picking.action_confirm or created_moves._action_confirm ?
        picking.action_confirm()
        # action confirm merges moves of the same product if merge=True
        #created_moves._action_confirm(merge=False) #TODO: picking or create_moves?

        # Use picking.action_assign or moves._action_assign to create move lines
        # Context variables:
        # - quant_ids:
        #   filters the quants that stock.quant._gather returns
        # - bypass_reservation_update:
        #   avoids to execute code specific for Odoo UI at stock.move.line.write()
        # TODO: picking.action_assign or created_moves._action_assign ?
        picking.with_context(quant_ids=quant_ids, bypass_reservation_update=True).action_assign()
        #created_moves.with_context(quant_ids=quant_ids, bypass_reservation_update=True)._action_assign()

        """
        # TODO: result_package
        # TODO: track_parent_package
        #       if it is false remove parent_id of the result_package_id ??
        # 1) create one operation per package_id in quants (corresponding to quant_ids)
           # if the package is in a parent_package e.g. pallet (pack_id.parent_id is set)
            # we have to set the result_package_id, otherwise we will lose
            # the parent package (e.g. pallet) info.
            if result_package_id:
                op_vals['result_package_id'] = result_package_id
            elif track_parent_package and pack.parent_id:
                op_vals['result_package_id'] = pack.parent_id.id
        # 2) create one operation for each product without packages
            # case where we are moving quants from A to B and they have to be in a package in location B
            if result_package_id:
                op_vals['result_package_id'] = result_package_id
        """

        return picking
