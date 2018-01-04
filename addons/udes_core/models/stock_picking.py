from odoo import models, fields
from odoo.exceptions import ValidationError

from ..common import check_many2one_validity, check_stock_of_quants_reserved


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def create_picking(
            self,
            quant_ids,
            location_id,
            location_dest_id=None,
            picking_id=None,
            result_package_id=None,
            track_parent_package=False,
            force_unreserve=False,
            linked=False,
            **kwargs
    ):
        """
        Creates or loads an internal transfer (stock.picking) for a package or
        quants in a location, to a destination location (default Stock)
        When this is called, reserve the operations (i.e. create
        stock move AND operation (stock.pack.operation), and set the
        reservation_id in the quant for the stock move's ID).

        :param quant_ids: ids (list/arrays of int) of [stock.quant] records, to
         be moved
        :param location_id: id (int) of a [stock.location[ record, the source
        location of the picking (Internal Transfer)
        :param location_dest_id: id (int) of a [stock.location] record, the
        destination location of the picking (Internal Transfer)
        :param picking_id: id (int) of a [stock.picking] record (the Internal
        Transfer). If this is specified, add the package(s)/quants to an existing
        internal transfer.
        :param result_package_id: id (int) of a [stock.quant.package] record (e.g. pallet).
        If this is specified, add the package(s)/quants to the corresponding parent package (e.g. pallet).
        :param track_parent_package: boolean to say if we want to track the parent
        package (e.g. pallet) of the package or not in the result_package_id of the [stock.pack.operation]
        record
        :param force_unreserve: boolean flag to force to unreserve the quants
            if they are reserved for any other transfer and their operations
            are not done.
        :param linked: boolean flag to say if the created transfer should be
            inserted into a chain of pickings.
        :return: the Internal Transfer ([stock.picking] record), in the same format
        as _list_data()

        Example:
        [{'id': 212680,
          'location_dest_id': 15,
          'name': u'INT10342',
          'origin': False,
          'packages': [],
          'picking_type_id': 5,
          'priority': u'1',
          'priority_name': 'Normal',
          'stock_pack_operations': [{'id': 1600211,
                                     'info': {'product_barcode': u'productApple',
                                              'product_display_name': u'[productApple] TestProduct Apple',
                                              'product_id': 268414,
                                              'requiresSerial': False},
                                     'location_barcode': u'LBASKET001',
                                     'location_dest_id': 15,
                                     'location_name': u'Fruit Basket',
                                     'lots': [],
                                     'operation_type': 'product',
                                     'package_id': False,
                                     'product_qty': 15.0,
                                     'qty_done': 15.0,
                                     'write_date': '2017-08-16 18:04:25'}]}]
        """
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        Product = self.env['product.product']
        Operation = self.env['stock.pack.operation']
        Quant = self.env['stock.quant']
        Location = self.env['stock.location']

        warehouse = self.env.user.get_user_warehouse()
        pick_type_internal = warehouse.int_type_id

        default_uom_id = self.env.ref('product.product_uom_unit').id

        # default Stock
        if location_dest_id is None:
            location_dest_id = warehouse.lot_stock_id.id

        # check params
        for (field, obj, id_) in [
            ('location_id', Location, location_id),
            ('location_dest_id', Location, location_dest_id),
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

        if picking_id is not None:
            picking = Picking.browse(picking_id)
            if picking.state in ('cancel', 'done'):
                raise ValidationError(_("The picking %s cannot be changed "
                                        "because it's %s") % (picking.name,
                                                              picking.state))
        else:
            vals = {
                'picking_type_id': pick_type_internal.id,
                'location_dest_id': location_dest_id,
                'location_id': location_id,
            }
            vals.update(kwargs)
            picking = Picking.create(vals)


        # when not creating a linked transfer, moves are created from quant info
        # when linked, moves are created from current moves info
        if not linked:
            # create stock move
            move_vals = [
                {
                    'name': 'INT/{} {}'.format(qty, Product.browse(product_id).name),
                    'product_id': product_id,
                    'product_uom_qty': qty,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'product_uom': default_uom_id,
                    'picking_id': picking.id,
                    'state': 'assigned',
                }
                for product_id, qty in group_qty_by_product(quants).items()
            ]
            for move_val in move_vals:
                move = Move.create(move_val)
                # "reserve" each quant with the same product as the move
                # to the move through the "reservation_id" field
                quants.filtered(
                    lambda q: q.product_id.id == move_val['product_id']
                ).write({'reservation_id': move.id})
        else:
            pass


        # 1) create one operation per package_id in quants (corresponding to quant_ids)
        #   future improvement: one operation per parent package if we have all the
        #   packages of the parent package (e.g. pallet) in the transfer
        #   where parent_package (e.g. pallet) = package_id.parent_id
        packages = quants.mapped('package_id')
        for pack in packages:
            op_vals = {
                'package_id': pack.id,
                'picking_id': picking.id,
                'location_id': location_id,
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
        # 2) create one operation for each product without packages
        quants_without_package = quants.filtered(lambda x: not x.package_id)
        for product, qty in group_qty_by_product(quants_without_package).items():
            op_vals = {
                'picking_id': picking.id,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
                'product_id': product,
                'product_uom_id': default_uom_id,
                'product_qty': qty,
            }
            # case where we are moving quants from A to B and they have to be in a package in location B
            if result_package_id:
                op_vals['result_package_id'] = result_package_id
            Operation.create(op_vals)

        # recompute quantities, to recompute the links (stock.move.operation.link)
        picking.do_recompute_remaining_quantities()
        # make the new_internal_transfer available
        picking.state = 'assigned'

        return picking._list_data()
