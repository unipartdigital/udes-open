# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_round


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def mark_as_done(self, location_dest=None, result_package=None, package=None, products_info=None):
        """
            location_dest = string or id
            result_package = string or id
            packge = string or id
            products_info = [{product_info}]
                where product_info = product_barcode, qty, damaged_qty, serial_numbers, damaged_serial_numbers
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
        if products_info:
            # prepare products_info
            products_info_by_product = move_lines._prepare_products_info(products_info)
            # filter move_lines by products in producst_info_by_product and undone
            move_lines = move_lines._filter_by_products_info(products_info_by_product)
            # filter unfinished move lines
            move_lines = move_lines.filtered(lambda ml: ml.qty_done < ml.product_uom_qty)
            move_lines._check_enough_quantity(products_info_by_product)
            # TODO: check this condition
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
        """ TODO:
        """
        # get all move lines of the products in products_info
        print(products_info)
        move_lines = self.filtered(lambda ml: ml.product_id in products_info)

        # if any of the products is tracked by serial number, filter if needed
        for product in move_lines.mapped('product_id').filtered(lambda ml: ml.tracking == 'serial'):
            serial_numbers = products_info[product]['serial_numbers']

            product_mls = move_lines.filtered(lambda ml: ml.product_id == product)
            mls_with_lot_id = product_mls.filtered(lambda ml: ml.lot_id)
            mls_with_lot_name = product_mls.filtered(lambda ml: ml.lot_name)
            if mls_with_lot_id:
                # all mls should have lot id
                if not mls_with_lot_id == product_mls:
                    raise ValidationError(
                            _("Some move lines don't have lot_id in "
                              "picking %s for product %s") %
                            (product_mls.mapped('picking_id.name'), product.name))

                product_mls_in_serial_numbers = mls_with_lot_id.filtered(lambda ml: ml.lot_id.name in serial_numbers)
                if len(product_mls_in_serial_numbers) != len(serial_numbers):
                    mls_serial_numbers = product_mls_in_serial_numbers.mapped('lot_id.name')
                    diff = set(serial_numbers) - set(mls_serial_numbers)
                    raise ValidationError(
                            _('Serial numbers %s for product %s not found in picking %s') %
                            (' '.join(diff), product.name, product_mls.mapped('picking_id.name')))

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
                            product_mls.mapped('picking_id.name'))
            elif product_mls:
                # new serial numbers
                pass
            else:
                # unexpected part?
                pass


        return move_lines

    def get_package_move_lines(self, package):
        """ Get move lines in self of package
        """
        return self.filtered(lambda ml: ml.package_id == package)

    def _assert_result_package(self, result_package):
        """ Checks that the result_package ....
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
        """ TODO check name, maybe do it different and move to another model

            For each key,value in info it merges to the corresponding
            produc info if it alreay exists.

            where key:
                qty, damaged_qty, serial_numbers, damaged_serial_numbers

            Only for products not tracked or tracked by serial numbers

            TODO: extend this function to handle damaged
        """
        if product.tracking == 'serial':
            if not 'serial_numbers' in info:
                raise ValidationError(
                        _('Validating a serial numbered product without'
                          ' serial numbers'))
            if len(info['serial_numbers']) != info['qty']:
                raise ValidationError(
                        _('The number of serial numbers and quantity done'
                          ' does not match for product %s') % product.name)
        if not product in products_info:
            products_info[product] = info.copy()
        else:
            for key, value in info:
                if isinstance(value, int) or isinstance(value,float):
                    products_info[product][key] += value
                elif isinstance(value, list):
                    products_info[product][key].append(value)
                else:
                    raise ValidationError(
                            _('Unexpected type for move line parameter %s') % key)

        return products_info

    def _check_enough_quantity(self, products_info):
        """ Check that move_lines in self can fulfill the quantity done
            in products_info, otherwise create unexpected parts if
            applicable.

            products_info is mapped by product and contains a dictionary
            with the qty to be marked as done and the list of serial
            numbers
        """
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
                # TODO: list of {'product_barcode': product.barcode, 'qty': diff} ?
                products_todo[product.id] = diff

        if products_todo:
            picking = self.mapped('picking_id')
            picking.add_unexpected_parts(products_todo)

    def _prepare_products_info(self, products_info):
        """ Reindex products_info by product.product model, merge repeated
            products info into one
        """
        Product = self.env['product.product']

        products_info_by_product = {}
        for info in products_info:
            product = Product.get_product(info['product_barcode'])
            products_info_by_product = self._update_products_info(product, products_info_by_product, info)

        return products_info_by_product


    def _prepare_line_product_info(self, values, products_info):
        """ Updates values and products_info....
        """
        # TODO: extend for damaged in a different module
        self.ensure_one()

        product = self.product_id
        info = products_info[product]
        qty_done = info['qty']

        if self.product_uom_qty < qty_done:
            qty_done = self.product_uom_qty
        values['qty_done'] = qty_done
        # update products_info remainint qty to be marked as done
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
                if ml_lot_name not in info['serial_numbers']:
                    raise ValidationError(
                            _('Cannot find serial number %s in the list'
                              ' of serial numbers to validate') %
                            ml_lot_name)
                i = info['serial_numbers'].index(ml_lot_name)
                # remove it from the list, no need to set lot_name because
                # the move line already has a lot_id
                info['serial_numbers'].pop(i)
            else:
                values['lot_name'] = info['serial_numbers'].pop()

        return (values, products_info)

    def _mark_as_done(self, values, split=True):
        """ Assumes all paramaters but lot numbers have been checked,
                    can we check lot numbers at _prepare_line_product_info?
        """
        self.ensure_one()
        if 'qty_done' not in values:
            raise ValidationError(
                    _('Cannot mark as done move line %s of picking %s without '
                      'quantity done') % (self.id, self.picking_id.name))

        self.write(values)
        if split:
            ml_done = self._split()
        else:
            ml_done = self

        return ml_done

    def _split(self):
        """ Split the move line in self if:
            - quantity done < quantity todo
            - quantity done > 0

            returns either self or the new move line
        """
        self.ensure_one()
        res = self
        if self.qty_done > 0 and float_compare(self.qty_done, self.product_uom_qty,
                                               precision_rounding=self.product_uom_id.rounding) < 0:
            quantity_left_todo = float_round(
                self.product_uom_qty - self.qty_done,
                precision_rounding=self.product_uom_id.rounding,
                rounding_method='UP')
            done_to_keep = self.qty_done
            # create new move line with the qty_done
            new_ml = self.copy(
                default={'product_uom_qty': done_to_keep,
                         'ordered_qty': done_to_keep,
                         'qty_done': self.qty_done,
                         })
            # update self move line quantity todo
            # - bypass_reservation_update:
            #   avoids to execute code specific for Odoo UI at stock.move.line.write()
            self.with_context(bypass_reservation_update=True).write(
                    {'product_uom_qty': quantity_left_todo,
                     'ordered_qty': quantity_left_todo,
                     'qty_done': 0.0,
                     'result_package_id': False,
                     })
            res = new_ml

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
            package_info = self.result_package_id.get_info()[0]

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
