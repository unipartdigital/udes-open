# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_round
from copy import deepcopy

from collections import Counter, defaultdict


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def get_lines_todo(self):
        """ Return the move lines in self that are not completed,
            i.e., quantity done < quantity todo
        """
        return self.filtered(lambda ml: ml.qty_done < ml.product_uom_qty)

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

        move_lines = self
        values = {}

        location = None
        if location_dest:
            # get the location to check if it is valid
            location = Location.get_location(location_dest)
            values['location_dest_id'] = location.id

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
            # TODO: check this condition, if it is not needed, we don't need package in this function
            if not package and not result_package and move_lines.mapped('package_id'):
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

        # TODO: at this point products_info_by_product should be with qty_todo = 0?
        #       No necessarily, can we have add unexpected parts and not enough stock?

        # it might be useful when extending the method
        return mls_done

    def _filter_by_products_info(self, products_info):
        """ Filter the move_lines in self by the products in product_ids.
            When a product is tracked by lot number:
            - when they have lot_id set, they are also filtered by
              serial number and check that they are not done
            - when they have lot_name, it is checked to avoid repeated
              serial numbers
        """
        # get all move lines of the products in products_info
        move_lines = self.filtered(lambda ml: ml.product_id in products_info)

        # if any of the products is tracked by serial number, filter if needed
        for product in move_lines.mapped('product_id').filtered(lambda ml: ml.tracking == 'serial'):
            serial_numbers = products_info[product]['lot_names']
            repeated_serial_numbers = [sn for sn, num in Counter(serial_numbers).items() if num > 1]
            if len(repeated_serial_numbers) > 0:
                raise ValidationError(
                            _('Serial numbers %s are repeated '
                              'in picking %s for product %s') %
                              (' '.join(repeated_serial_numbers),
                               move_lines.mapped('picking_id').name,
                               product.name))

            product_mls = move_lines.filtered(lambda ml: ml.product_id == product)
            mls_with_lot_id = product_mls.filtered(lambda ml: ml.lot_id)
            mls_with_lot_name = product_mls.filtered(lambda ml: ml.lot_name)
            if mls_with_lot_id:
                # all mls should have lot id
                if not mls_with_lot_id == product_mls:
                    raise ValidationError(
                            _("Some move lines don't have lot_id in "
                              "picking %s for product %s") %
                            (product_mls.mapped('picking_id').name, product.name))

                product_mls_in_serial_numbers = mls_with_lot_id.filtered(lambda ml: ml.lot_id.name in serial_numbers)
                if len(product_mls_in_serial_numbers) != len(serial_numbers):
                    mls_serial_numbers = product_mls_in_serial_numbers.mapped('lot_id.name')
                    diff = set(serial_numbers) - set(mls_serial_numbers)
                    raise ValidationError(
                            _('Serial numbers %s for product %s not found in picking %s') %
                            (' '.join(diff), product.name, product_mls.mapped('picking_id').name))

                done_mls = product_mls_in_serial_numbers.filtered(lambda ml: ml.qty_done > 0)
                if done_mls:
                    raise ValidationError(
                            _("Operations for product %s with serial "
                              "numbers %s are already done.") %
                            (product.name, ','.join(done_mls.mapped('lot_id.name'))))

                product_mls_not_in_serial_numbers = product_mls - product_mls_in_serial_numbers
                # remove move lines not in serial_numbers
                move_lines -= product_mls_not_in_serial_numbers

            elif mls_with_lot_name:
                # none of them has lot id, so they are new serial numbers and
                # none of them
                product_mls_in_serial_numbers = mls_with_lot_name.filtered(lambda ml: ml.lot_name in serial_numbers)
                if product_mls_in_serial_numbers:
                    raise ValidationError(
                            _('Serial numbers %s already exist in picking %s') %
                            (' '.join(product_mls_in_serial_numbers.mapped('lot_name')),

                            product_mls.mapped('picking_id').name))
                product.assert_serial_numbers(serial_numbers)
            elif product_mls:
                # new serial numbers
                product.assert_serial_numbers(serial_numbers)
            else:
                # unexpected part?
                pass

        return move_lines

    def get_package_move_lines(self, package):
        """ Get move lines in self of package
        """
        return self.filtered(lambda ml: ml.package_id == package)

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
            produc info if it alreay exists.

            where key:
                qty, serial_numbers

            Only for products not tracked or tracked by serial numbers

            TODO: extend this function to handle damaged
                damaged_qty, damaged_serial_numbers
        """
        if product.tracking == 'serial':
            if not 'lot_names' in info:
                raise ValidationError(
                        _('Validating a serial numbered product without'
                          ' serial numbers'))
            if len(info['lot_names']) != info['qty']:
                raise ValidationError(
                        _('The number of serial numbers and quantity done'
                          ' does not match for product %s') % product.name)

        if not product in products_info:
            products_info[product] = info.copy()
        else:
            for key, value in info.items():
                if isinstance(value, int) or isinstance(value,float):
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

        if product.tracking == 'serial':
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
                            _('Cannot find serial number %s in the list'
                              ' of serial numbers to validate') %
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
        '''This function computes the different product quantities for the given move_lines
        '''
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
            - qty_done: float
            - result_package_id: {stock.quant.package}
            - write_date: datetime
        """
        self.ensure_one()

        package_info = False
        result_package_info = False
        if self.package_id:
            package_info = self.package_id.get_info()[0]
        if self.result_package_id:
            result_package_info = self.result_package_id.get_info()[0]

        return {"id": self.id,
                "create_date": self.create_date,
                "location_id": self.location_id.get_info()[0],
                "location_dest_id": self.location_dest_id.get_info()[0],
                #"lot_id": self.lot_id.id,
                "package_id": package_info,
                "result_package_id": result_package_info,
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
