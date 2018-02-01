# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError

# TODO: add enumeration for pallet_products, etc

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def mark_as_done(self, location_dest=None, result_package=None, package=None, products_info=None):
        """ Extend mark_as_done function to handle another level of packages and
            use u_target_storage_format.
        """
        result_package, parent_package = \
                self._prepare_result_packages(package, result_package, products_info)

        res = super(StockMoveLine, self).mark_as_done(location_dest=location_dest,
                                                      result_package=result_package,
                                                      package=package,
                                                      products_info=products_info)

        if parent_package:
            res.write({'u_result_parent_package_id': parent_package.id})

        return res

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
                # It migt be a new pallet id
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
            if result_package and not package:
                # Moving stock into a pallet of products, result_package
                # might be new pallet id
                result_package = Package.get_package(result_package, create=True).name

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

    def get_package_move_lines(self, package):
        """ Extend to get move lines of package when package is
            a parent package and to handle swapping packages.
        """
        if package.children_ids:
            res = self.filtered(lambda ml: ml.package_id in package.children_ids)
        else:
            res = super(StockMoveLine, self).get_package_move_lines(package)

        if not res:
            # The package is not found in the move lines,
            # check if the package can be swapped and get
            # move_lines
            picking = self.mapped('picking_id')
            res = picking.handle_swap(package)

        return res
