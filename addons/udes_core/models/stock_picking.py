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
            TODO
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

        # check params
        for (field, obj, id_) in [
            ('location_id', Location, location_id),
            ('location_dest_id', Location, location_dest_id),
            ('picking_location_dest_id', Location, picking_location_dest_id),
        ]:
            check_many2one_validity(field, obj, id_)
        if picking_id is not None:
            check_many2one_validity('picking_id', Picking, picking_id)

        quants = Quant.browse(quant_ids)

        if linked:
            # TODO: store info for creating linked transfer.
            pass

        if force_unreserve:
            # TODO: Implement
            pass

        quants.ensure_not_reserved()
        quants.ensure_entire_packages()
        # TODO: probably not needed anymore
        #self.hook_for_check_before_create_picking(quants)

        if picking_id is not None:
            picking = Picking.browse(picking_id)
            if picking.state in ('cancel', 'done'):
                raise ValidationError(_("The picking %s cannot be changed "
                                        "because it's %s") % (picking.name,
                                                              picking.state))
            # reuse the group of the transfer
            group_id = picking.group_id.id
        else:
            # transfer needs to be created
            vals = {
                'picking_type_id': picking_type.id,
                'location_dest_id': picking_location_dest_id,
                'location_id': location_id,
                'group_id': group_id,
            }
            vals.update(kwargs)
            picking = Picking.create(vals)


        # when not creating a linked transfer, moves are created from quant info
        # when linked, moves are created from current moves info
        created_moves = Move.browse()
        if not linked:
            # create stock move
            # TODO: get all the display_names with one call to DB?
            move_vals = [
                {
                    'name': '{} {}'.format(qty, Product.browse(product_id).display_name),
                    'product_id': product_id,
                    'product_uom_qty': qty,
                    'location_id': location_id,
                    'location_dest_id': picking_location_dest_id,
                    'product_uom': default_uom_id,
                    'picking_id': picking.id,
                    'group_id': group_id,
                }
                # TODO: create a function at quants that returns the group ?
                for product_id, qty in group_qty_by_product(quants).items()
            ]
            for move_val in move_vals:
                move = Move.create(move_val)
                created_moves |= move
        else:
            # TODO: implement or merge with other code
            pass


        # call action_confirm:
        # - chain of moves will be created if needed
        # - procurement group will be created if needed (this needs u_create_group)
        # TODO: migrate picking_type.u_create_group and extend action_confirm
        #       probably not needed for stock move
        #TODO: picking.action_confirm or created_moves._action_confirm ?
        picking.action_confirm()
        # action confirm merges moves of the same product if merge=True
        #created_moves._action_confirm(merge=False) #TODO: picking or create_moves?

        # Use picking.action_assign or moves._action_assign to create move lines
        # Context variables:
        # - quant_ids:
        #   filters the quants that stock.quant._gather returns
        # - bypass_reservation_update:
        #   avoids to execute code specific for Odoo UI at stock.move.line.write()
        move_lines_before = picking.move_line_ids
        #TODO: picking.action_assign or created_moves._action_assign ?
        picking.with_context(quant_ids=quant_ids, bypass_reservation_update=True).action_assign()
        #created_moves.with_context(quant_ids=quant_ids, bypass_reservation_update=True)._action_assign()
        move_lines_after = picking.move_line_ids - move_lines_before
        # set location_dest_id of the new move lines
        move_lines_after.write({'location_dest_id': location_dest_id})

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

        if force_picking_dest_id:
            picking.location_dest_id = location_dest_id

        return picking
