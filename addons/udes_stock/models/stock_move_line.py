# -*- coding: utf-8 -*-
from itertools import groupby

from odoo import api, fields, models,  _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_round
from copy import deepcopy
from collections import Counter, defaultdict


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    u_grouping_key = fields.Char('Key', compute='compute_grouping_key')


    def get_lines_todo(self):
        """ Return the move lines in self that are not completed,
            i.e., quantity done < quantity todo
        """
        return self.filtered(lambda ml: ml.qty_done < ml.product_uom_qty)

    def get_lines_done(self):
        """ Return the move lines in self that are completed,
            i.e., quantity done == quantity todo
        """
        return self.filtered(lambda ml: ml.qty_done == ml.product_uom_qty)

    def _prepare_result_packages(self, package, result_package, products_info):
        """ Compute result_package and result_parent based on the
            u_target_Storage_format of the picking type + the input
            parameters.
        """
        Package = self.env['stock.quant.package']

        parent_package = None

        # atm mark_as_done is only called per picking
        picking = self.mapped('picking_id')
        picking.ensure_one()
        target_storage_format = picking.picking_type_id.u_target_storage_format

        if target_storage_format == 'pallet_packages':
            if result_package:
                # At pallet_packages, result_package parameter is expected
                # to be the result_parent_package of the move_line
                # It might be a new pallet id
                parent_package = Package.get_package(result_package, create=True)
                result_package = None
                if not package:
                    if products_info:
                        # Products are being packed
                        result_package = Package.create({}).name
                    elif not all([ml.result_package_id for ml in self]):
                        # Setting result_parent_package expects to have
                        # result_package for all the move lines
                        raise ValidationError(
                                _("Some of the move lines don't have result package."))
            elif products_info:
                raise ValidationError(
                        _('Invalid parameters for target storage format,'
                          ' expecting result package.'))

        elif target_storage_format == 'pallet_products':
            if result_package:
                # Moving stock into a pallet of products, result_package
                # might be new pallet id
                result_package = Package.get_package(result_package, create=True).name
            elif products_info and not result_package:
                raise ValidationError(
                        _('Invalid parameters for target storage format,'
                          ' expecting result package.'))

        elif target_storage_format == 'package':
            if products_info and not package and not result_package:
                # Mark_as_done products without package or result_package
                # Create result_package when packing products without
                # result_package being set
                result_package = Package.create({}).name

        elif target_storage_format == 'product':
            # Error when trying to mark_as_done a full package or setting result package
            # when result storage format is products
            if result_package or (package and not products_info):
                raise ValidationError(
                        _('Invalid parameters for products target'
                          ' storage format.'))

        return (result_package, parent_package)

    def mark_as_done(self, location_dest=None, result_package=None, package=None, product_ids=None):
        """ Marks as done the move lines in self and updates location_dest_id
            and result_package_id if they are set.

            When product_ids is set, only matching move lines from self will
            be marked as done for a specific quantity.

            - location_dest = string or id
            - result_package = string or id
            - package = string or id
            - product_ids = list of dictionaries, whose keys will be
                              barcode, qty, lot_names
        """
        MoveLine = self.env['stock.move.line']
        Location = self.env['stock.location']
        Package = self.env['stock.quant.package']

        result_package, parent_package = \
            self._prepare_result_packages(package, result_package, product_ids)

        move_lines = self
        values = {}
        loc_dest_instance = None

        if location_dest is not None:
            # NB: checking if the dest loc is valid; better erroring
            # sooner than later (we'll write the new loc dest below)
            loc_dest_instance = Location.get_location(location_dest)
            picking = self.mapped('picking_id')

            if not picking.is_valid_location_dest_id(loc_dest_instance):
                raise ValidationError(
                    _("The location '%s' is not a child of the picking destination "
                      "location '%s'" % (loc_dest_instance.name, picking.location_dest_id.name)))

        if result_package:
            # get the result package to check if it is valid
            result_package = Package.get_package(result_package)
            values['result_package_id'] = result_package.id

        if package:
            # get the package
            package = Package.get_package(package)

        products_info_by_product = {}
        if product_ids:
            # TODO: move functions into picking instead of parameter
            picking = move_lines.mapped('picking_id')
            # prepare products_info
            products_info_by_product = move_lines._prepare_products_info(deepcopy(product_ids))
            # filter move_lines by products in producst_info_by_product and undone
            move_lines = move_lines._filter_by_products_info(products_info_by_product)
            # filter unfinished move lines
            move_lines = move_lines.get_lines_todo()
            # TODO all in one function?
            move_lines = move_lines._check_enough_quantity(products_info_by_product, picking_id=picking)

            if not package and move_lines.mapped('package_id'):
                raise ValidationError(_('Setting as done package operations as product operations'))

        if not move_lines:
            raise ValidationError(_("Cannot find move lines to mark as done"))

        if move_lines.filtered(lambda ml: ml.qty_done > 0):
            raise ValidationError(_("The operation is already done"))

        # check valid result_package for the move_lines that are going
        # to be marked as done only
        move_lines._assert_result_package(result_package)

        mls_done = MoveLine.browse()
        for ml in move_lines:
            ml_values = values.copy()
            # Check if there is specific info for the move_line product
            # otherwise we fully mark as done the move_line
            if products_info_by_product:
                # check if the qty done has been fulfilled
                if products_info_by_product[ml.product_id]['qty'] == 0:
                    continue
                ml_values, products_info_by_product = ml._prepare_line_product_info(ml_values, products_info_by_product)
            else:
                ml_values['qty_done'] = ml.product_qty
            mls_done |= ml._mark_as_done(ml_values)

        if loc_dest_instance is not None:
            # HERE(ale): updating the dest loc here to have a single
            # invocation of its constraint handler (see below)
            mls_done.write({'location_dest_id': loc_dest_instance.id})

        # TODO: at this point products_info_by_product should be with qty_todo = 0?
        #       No necessarily, can we have add unexpected parts and not enough stock?

        # it might be useful when extending the method
        if parent_package:
            mls_done.write({'u_result_parent_package_id': parent_package.id})

        return mls_done

    def _filter_by_products_info(self, products_info):
        """ Filter the move_lines in self by the products in product_ids.
            When a product is tracked by lot number:
            - when they have lot_id set, they are also filtered by
              lot number and check that they are not done
            - when they have lot_name, it is checked to avoid repeated
              lot numbers
        """
        # get all move lines of the products in products_info
        move_lines = self.filtered(lambda ml: ml.product_id in products_info)

        # if any of the products is tracked by lot number, filter if needed
        for product in move_lines.mapped('product_id').filtered(lambda ml: ml.tracking != 'none'):
            lot_numbers = products_info[product]['lot_names']
            repeated_lot_numbers = [sn for sn, num in Counter(lot_numbers).items() if num > 1]
            if len(repeated_lot_numbers) > 0:
                raise ValidationError(
                    _('Lot numbers %s are repeated in picking %s for '
                      'product %s') % (' '.join(repeated_lot_numbers),
                                       move_lines.mapped('picking_id').name,
                                       product.name))

            product_mls = move_lines.filtered(lambda ml: ml.product_id == product)
            mls_with_lot_id = product_mls.filtered(lambda ml: ml.lot_id)
            mls_with_lot_name = product_mls.filtered(lambda ml: ml.lot_name)
            if mls_with_lot_id:
                # all mls should have lot id
                if not mls_with_lot_id == product_mls:
                    raise ValidationError(
                        _("Some move lines don't have lot_id in picking %s for "
                          "product %s") %
                        (product_mls.mapped('picking_id').name, product.name))

                product_mls_in_lot_numbers = mls_with_lot_id.filtered(lambda ml: ml.lot_id.name in lot_numbers)
                if len(product_mls_in_lot_numbers) != len(lot_numbers):
                    mls_lot_numbers = product_mls_in_lot_numbers.mapped('lot_id.name')
                    diff = set(lot_numbers) - set(mls_lot_numbers)
                    raise ValidationError(
                        _('Lot numbers %s for product %s not found in '
                          'picking %s') %
                        (' '.join(diff), product.name,
                         product_mls.mapped('picking_id').name))

                done_mls = product_mls_in_lot_numbers.filtered(lambda ml: ml.qty_done > 0)
                if done_mls:
                    raise ValidationError(
                        _("Operations for product %s with lot numbers %s are "
                          "already done.") %
                        (product.name,
                         ','.join(done_mls.mapped('lot_id.name'))))

                product_mls_not_in_lot_numbers = product_mls - product_mls_in_lot_numbers
                # remove move lines not in lot_numbers
                move_lines -= product_mls_not_in_lot_numbers

            elif mls_with_lot_name:
                # none of them has lot id, so they are new lot numbers
                product_mls_in_lot_numbers = mls_with_lot_name.filtered(lambda ml: ml.lot_name in lot_numbers)
                if product.tracking == 'serial' and product_mls_in_lot_numbers:
                    raise ValidationError(
                        _('Serial numbers %s already exist in picking %s') %
                        (' '.join(product_mls_in_lot_numbers.mapped('lot_name')),
                         product_mls.mapped('picking_id').name))
                product.assert_serial_numbers(lot_numbers)
            elif product_mls:
                # new serial numbers
                product.assert_serial_numbers(lot_numbers)
            else:
                # unexpected part?
                pass

        return move_lines

    def get_package_move_lines(self, package):
        """ Get move lines of package when package is a package or
            a parent package, and to handle swapping packages in
            case the expected_package_name entry is included in
            the context.

        """
        Package = self.env['stock.quant.package']

        package.ensure_one()
        move_lines = None
        expected_package_name = self.env.context.get('expected_package_name')
        picking = self.mapped('picking_id')

        if expected_package_name is not None \
           and expected_package_name != package.name:
            expected_package = Package.get_package(expected_package_name)
            move_lines = picking.maybe_swap(package, expected_package)

        if move_lines is None:
            if package.children_ids:
                move_lines = self.filtered(
                    lambda ml: ml.package_id in package.children_ids)
            else:
                move_lines = self.filtered(lambda ml: ml.package_id == package)

        if not move_lines:
            raise ValidationError(
                    _("Package %s not found in the operations of picking '%s'")
                    % (package.name, picking.name))

        return move_lines


    def _assert_result_package(self, result_package):
        """ Checks that result_package is the expected result package
            for the move lines in self. i.e., result_package has to
            match with move_line.result_package_id.
        """
        if not result_package:
            return
        for ml in self:
            ml_result_package = ml.result_package_id
            if not ml.package_id and ml_result_package and\
                    result_package != ml_result_package:
                # only when not ml.package_id because it means that what we
                # have in ml.result_package_id is the expected result package
                raise ValidationError(
                        _('A container (%s) already exists for the operation'
                          ' but you are using another one (%s)' %
                          (ml_result_package.name, result_package.name)))

    def _update_products_info(self, product, products_info, info):
        """ For each (key, value) in info it merges to the corresponding
            product info if it already exists.

            where key:
                qty, lot_names

            Only for products not tracked or tracked by serial numbers

            TODO: extend this function to handle damaged
                damaged_qty, damaged_serial_numbers
        """
        tracking = product.tracking
        if tracking != 'none':
            if 'lot_names' not in info:
                raise ValidationError(
                        _('Missing tracking info for product %s tracked by %s')
                          % (product.name, tracking))
            if tracking == 'serial' and \
                    len(info['lot_names']) != info['qty']:
                raise ValidationError(
                        _('The number of serial numbers and quantity done'
                          ' does not match for product %s') % product.name)

        if not product in products_info:
            products_info[product] = info.copy()
        else:
            for key, value in info.items():
                if isinstance(value, int) or isinstance(value, float):
                    products_info[product][key] += value
                elif isinstance(value, list):
                    products_info[product][key].extend(value)
                else:
                    raise ValidationError(
                            _('Unexpected type for move line parameter %s') % key)

        return products_info

    def _check_enough_quantity(self, products_info, picking_id=None):
        """ Check that move_lines in self can fulfill the quantity done
            in products_info, otherwise create unexpected parts if
            applicable.

            products_info is mapped by product and contains a dictionary
            with the qty to be marked as done and the list of serial
            numbers
        """
        move_lines = self
        # products_todo stores extra quantity done per product that
        # cannot be handled in the move lines in self
        products_todo = {}
        for product, info in products_info.items():
            product_mls = self.filtered(lambda ml: ml.product_id == product)
            mls_qty_reserved = sum(product_mls.mapped('product_uom_qty'))
            mls_qty_done = sum(product_mls.mapped('qty_done'))
            mls_qty_todo = mls_qty_reserved - mls_qty_done
            qty_done = info['qty']
            diff = mls_qty_todo - qty_done
            if diff < 0:
                #not enough quantity
                products_todo[product.id] = abs(diff)

        if products_todo:
            # TODO: move function into picking?
            # if not move_line in self, there is no picking
            picking = self.mapped('picking_id') or picking_id
            new_move_lines = picking.add_unexpected_parts(products_todo)
            move_lines |= new_move_lines

        return move_lines

    def _prepare_products_info(self, product_ids):
        """ Reindex products_info by product.product model, merge repeated
            products info into one
        """
        Product = self.env['product.product']

        products_info_by_product = {}
        for info in product_ids:
            product = Product.get_product(info['barcode'])
            del info['barcode']
            products_info_by_product = self._update_products_info(product, products_info_by_product, info)
        return products_info_by_product


    def _prepare_line_product_info(self, values, products_info):
        """ Updates values with the proper quantity done and optionally
            with a serial number, and updates products_info according
            to it by decreasing the remaining quantity to be done
        """
        # TODO: extend for damaged in a different module
        self.ensure_one()

        product = self.product_id
        info = products_info[product]
        qty_done = info['qty']

        if self.product_uom_qty < qty_done:
            qty_done = self.product_uom_qty
        values['qty_done'] = qty_done
        # update products_info remaining qty to be marked as done
        info['qty'] -= qty_done

        if product.tracking != 'none':
            if self.lot_name:
                # lot_name is set when it does not exist in the system
                raise ValidationError(
                        _("Trying to mark as done a move line with lot"
                          " name already set: %s") % self.lot_name)
            # lot_id is set when it already exists in the system
            ml_lot_name = self.lot_id.name
            if ml_lot_name:
                # check that is in the serial numbers list
                if ml_lot_name not in info['lot_names']:
                    raise ValidationError(
                            _('Cannot find lot number %s in the list'
                              ' of lot numbers to validate') %
                            ml_lot_name)
                i = info['lot_names'].index(ml_lot_name)
                # remove it from the list, no need to set lot_name because
                # the move line already has a lot_id
                info['lot_names'].pop(i)
            else:
                values['lot_name'] = info['lot_names'].pop()

        return (values, products_info)

    def _mark_as_done(self, values, split=True):
        """ Upate the move line with values and splits it if needed.
        """
        self.ensure_one()
        if 'qty_done' not in values:
            raise ValidationError(
                    _('Cannot mark as done move line %s of picking %s without '
                      'quantity done') % (self.id, self.picking_id.name))

        self.write(values)
        if split:
            self._split()

        return self

    def _split(self):
        """ Split the move line in self if:
            - quantity done < quantity todo
            - quantity done > 0

            returns either self or the new move line
        """
        self.ensure_one()
        res = self
        qty_done = self.qty_done
        if qty_done > 0 and float_compare(qty_done, self.product_uom_qty,
                                          precision_rounding=self.product_uom_id.rounding) < 0:
            quantity_left_todo = float_round(
                self.product_uom_qty - qty_done,
                precision_rounding=self.product_uom_id.rounding,
                rounding_method='UP')
            ordered_quantity_left_todo = quantity_left_todo
            done_to_keep = qty_done
            ordered_qty = qty_done
            if qty_done > self.ordered_qty:
                ordered_qty = self.ordered_qty
                ordered_quantity_left_todo = 0

            # create new move line with the qty_done
            new_ml = self.copy(
                    default={'product_uom_qty': quantity_left_todo,
                             'ordered_qty': ordered_quantity_left_todo,
                             'qty_done': 0.0,
                             'result_package_id': False,
                             'lot_name': False,
                    })
            # updated ordered_qty otherwise odoo will use product_uom_qty
            # new_ml.ordered_qty = ordered_quantity_left_todo
            # update self move line quantity todo
            # - bypass_reservation_update:
            #   avoids to execute code specific for Odoo UI at stock.move.line.write()
            self.with_context(bypass_reservation_update=True).write(
                        {'product_uom_qty': done_to_keep,
                         'qty_done': qty_done,
                         })
            self.ordered_qty = ordered_qty
            res = new_ml

        return res

    def _get_all_products_quantities(self):
        """This function computes the different product quantities for the given move_lines
        """
        res = defaultdict(int)
        for move_line in self:
            res[move_line.product_id] += move_line.product_uom_qty
        return res

    def _prepare_info(self):
        """
            Prepares the following info of the move line self:
            - id: int
            - create_date: datetime
            - location_dest_id: {stock.lcation}
            - location_id: {stock.lcation}
            - lot_id: TBC
            - package_id: {stock.quant.package}
            - result_package_id: {stock.quant.package}
            - u_result_parent_package_id: {stock.quant.package}
            - product_uom_qty: float
            - qty_done: float
            - write_date: datetime
        """
        self.ensure_one()

        package_info = False
        result_package_info = False
        result_parent_package_info = False
        if self.package_id:
            package_info = self.package_id.get_info()[0]
        if self.result_package_id:
            result_package_info = self.result_package_id.get_info()[0]
        if self.u_result_parent_package_id:
            result_parent_package_info = self.u_result_parent_package_id.get_info()[0]

        return {"id": self.id,
                "create_date": self.create_date,
                "location_id": self.location_id.get_info()[0],
                "location_dest_id": self.location_dest_id.get_info()[0],
                #"lot_id": self.lot_id.id,
                "package_id": package_info,
                "result_package_id": result_package_info,
                "u_result_parent_package_id": result_parent_package_info,
                "product_uom_qty": self.product_uom_qty,
                "qty_done": self.qty_done,
                "write_date": self.write_date,
               }

    def get_info(self):
        """ Return a list with the information of each move line in self.
        """
        res = []
        for line in self:
            res.append(line._prepare_info())

        return res

    def sort_by_location_product(self, state=None):
        """ Sort the move lines
        """
        MoveLine = self.env['stock.move.line']

        mls = self

        if state is None:
            pass
        elif state == 'done':
            mls = mls.get_lines_done()
        elif state == 'not_done':
            mls = mls.get_lines_todo()
        else:
            raise AssertionError('State not valid to sort tasks')

        return mls.sorted(key=lambda x: (x.location_id.name, x.product_id.id))

    def get_quants(self):
        """ Returns the quants related to move lines in self
        """
        Quant = self.env['stock.quant']

        quants = Quant.browse()
        for ml in self:
            quants |= Quant._gather(ml.product_id, ml.location_id,
                                    lot_id=ml.lot_id, package_id=ml.package_id,
                                    owner_id=ml.owner_id, strict=True)

        return quants

    def _prepare_task_info(self):
        """ Prepares info of a task
        """
        picking = self.mapped('picking_id')
        picking.ensure_one()
        task = {
            'picking_id': picking.id,
        }
        user_scans = picking.picking_type_id.u_user_scans
        if user_scans == 'product':
            task['pick_quantity'] = sum(self.mapped('product_qty'))
            quant = self.get_quants()
            task['quant_id'] = quant.get_info()[0]
            task['product_packaging'] = self.move_id.\
                                        sale_line_id.product_packaging.name

        else:
            package = self.mapped('package_id')
            package.ensure_one()
            info = package.get_info(extended=True)
            if not info:
                raise ValidationError(
                    _('Expecting package information for next task to pick,'
                      ' but move line does not contain it. Contact team'
                      'leader and check picking %s') % picking.name
                )
            task['package_id'] = info[0]

        return task

    def compute_grouping_key(self):
        for ml in self:
            ml_vals = {fname: getattr(ml, fname)
                       for fname in ml._fields.keys()}
            format_str = ml.picking_id.picking_type_id.u_move_line_key_format

            if format_str:
                ml.u_grouping_key = format_str.format(**ml_vals)
            else:
                ml.u_grouping_key = None

    def group_by_key(self):
        # force recompute on u_grouping_key so we have an up-to-date key:
        self._fields['u_grouping_key'].compute_value(self)

        if any(pt.u_move_line_key_format is False
               for pt in self.mapped('picking_id.picking_type_id')):
            raise UserError(_("Cannot group move lines when their picking type"
                              "has no grouping key set."))

        by_key = lambda ml: ml.u_grouping_key
        return {k: self.browse([ml.id for ml in g])
                for k, g in
                groupby(sorted(self, key=by_key), key=by_key)}

    #
    ## Drop Location Constraint
    #

    @api.constrains('location_dest_id')
    def _validate_location_dest(self):
        """ Ensures that the location destination is a child of the
            default_location_dest_id of the picking.
        """
        location = self.mapped('location_dest_id')

        # HERE(ale): iterating picking_id even if it's a many2one
        # because the constraint can be triggered anywhere
        for picking in self.mapped('picking_id'):
            if not picking.is_valid_location_dest_id(location=location):
                raise ValidationError(
                    _("The location '%s' is not a child of the picking destination "
                      "location '%s'" % (location.name, picking.location_dest_id.name)))
