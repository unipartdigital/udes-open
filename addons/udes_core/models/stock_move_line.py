# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_round

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def validate(self, location_dest=None, result_package=None, package=None, products_info=None):
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
        # TODO: self.check_valid_location_dest(location_dest)

        if result_package:
            # get the result package to check if it is valid
            result_package = Package.get_package(result_package)
            values['result_package_id'] = result_package.id

        if package:
            # get the package and filter move_lines of the package
            package = Package.get_package(package)
            move_lines = move_lines.get_package_move_lines(package)

        products_info_by_product = {}
        if products_info:
            # prepare products_info and filter move_lines by the product in it
            products_info_by_product = move_lines._prepare_products_info(products_info)
            move_lines = move_lines.filtered(lambda ml: ml.product_id in products_info_by_product and
                                                        ml.qty_done == 0)
            # TODO: check this condition
            if not package and not result_package and move_lines.mapped('package_id'):
                raise ValidationError(_('Setting as done package operations as product operations'))

        if not move_lines:
            raise ValidationError(_("Cannot find move lines to validate"))
        if move_lines.filtered(lambda ml: ml.qty_done > 0):
            raise ValidationError(_("The operation is already done"))

        # check valid result_package for the move_lines that are going
        # to be validated only
        move_lines._assert_result_package(result_package)

        mls_done = MoveLine.browse()
        for ml in move_lines:
            ml_values = values.copy()
            if products_info_by_product:
                # there is specific info for the product of the move_line
                ml._prepare_line_product_info(ml_values, products_info_by_product)
            else:
                # otherwise we fully validate the move_line
                ml_values['qty_done'] = ml.product_qty
            mls_done |= ml._validate(ml_values)

        # TODO: at this point products_info_by_product should be with qty_todo = 0?
        #       check it?

        # it might be useful when extending the method
        return mls_done

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


    def _set_products_info(self, product, products_info, info):
        """ TODO check name, maybe do it different and move to another model

            For each key,value in info it merges to the corresponding
            produc info if it alreay exists.

            where key:
                qty, damaged_qty, serial_numbers, damaged_serial_numbers

            Only for products not tracked or tracked by serial numbers
        """
        if product.tracking == 'serial' and not 'serial_numbers' in info:
            raise ValidationError(_('Validating a serial numbered product without serial numbers'))

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

    def _check_enough_quantity(self, products_info):
        """ Checks if there is enough quantity todo at move_lines in self
            to fulfill the qty_done of all products

            Also checks if qty_done = len(serial_numbers)
        """
        products_todo = {}
        for product, info in products_info.items():
            qty_todo = sum(self.filtered(lambda ml: ml.product_id == product).mapped('product_qty'))
            qty_done = info['qty']
            diff = qty_todo - qty_done
            if diff >= 0:
                # TODO: do the same for damaged serial nubmers overriding this function
                if product.tracking == 'serial' and qty_done != len(info['serial_numbers']):
                    raise ValidationError(
                        _('The number of serial numbers and quantity done'
                          ' does not match for product %s') % product.name)
            else:
                #not enough quantity
                # TODO: list of {'product_barcode': product.barcode, 'qty': diff} ?
                products_todo[product.id] = diff

        if products_todo:
            picking = self.mapped('picking_id')
            picking.add_unexpected_parts(products_todo)

    def _prepare_products_info(self, products_info):
        """ Reindex products_info by product.product model, merge repeated
            products info into one and check that move_lines in self can
            fulfill the quantity done (otherwise create unexpected parts
            if applicable)
        """
        Product = self.env['product.product']

        products_info_by_product = {}
        for info in products_info:
            product = Product.get_product(info['product_barcode'])
            self._set_products_info(product, products_info_by_product, info)

        self._check_enough_quantity(products_info_by_product)

        return products_info_by_product


    def _prepare_line_product_info(self, values, products_info):
        # TODO: extend for damaged in a different module
        self.ensure_one()

        product = self.product_id
        info = products_info[product]
        qty_done = info['qty']

        if self.product_qty < qty_done:
            qty_done = self.product_qty
        values['qty_done'] = qty_done
        # update products_info qty todo
        info['qty'] -= qty_done

        if product.tracking == 'serial':
            # lot_id is when it already exists in the system
            ml_lot_name = self.lot_name or self.lot_id.name
            # TODO: when ml_lot_name is set, pop the corresponding,
            #       it has to match to one of them
            values['lot_name'] = info['serial_numbers'].pop()

    def _validate(self, values, split=True):
        """ Assumes all paramaters but lot numbers have been checked,
                    can we check lot numbers at _prepare_line_product_info?
        """
        self.ensure_one()
        if 'qty_done' not in values:
            raise ValidationError(
                    _('Cannot validate move line %s of picking %s without '
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
            new_ml = self.copy(
                default={'product_uom_qty': 0, 'qty_done': self.qty_done})
            self.write({'product_uom_qty': quantity_left_todo,
                        'qty_done': 0.0,
                        'result_package_id': False})
            new_ml.write({'product_uom_qty': done_to_keep})
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
