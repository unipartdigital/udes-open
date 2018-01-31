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
                self._prepare_packages(package, result_package, products_info)

        res = super(StockMoveLine, self).mark_as_done(location_dest=location_dest,
                                                  result_package=result_package,
                                                  package=package,
                                                  products_info=products_info)

        if parent_package:
            res.write({'u_result_parent_package_id': parent_package.id})

        return res

    def _prepare_packages(self, package, result_package, products_info):
        # TODO: outer if should be target storage format since it is
        #       what defines the logic of the parameters

        Package = self.env['stock.quant.package']

        # atm mark_as_done is only called per picking
        picking = self.mapped('picking_id')
        picking.ensure_one()

        target_storage_format = picking.picking_type_id.u_target_storage_format

        parent_package = None
        # error when trying to mark_as_done a full package or setting result package
        # when result storage format is products
        if (result_package or (package and not products_info)) and \
                target_storage_format == 'product':
            raise ValidationError(
                    _('Invalid parameters for target storage format.'))

        if result_package:
            if target_storage_format == 'pallet_packages':
                parent_package = Package.get_package(result_package, create=True)
                result_package = None
                if not package:
                    if products_info:
                        # we are packing
                        result_package = Package.create({}).name
                    elif not all([ml.result_package_id for ml in self]):
                       raise ValidationError(_("Some of the move lines don't have result package."))

            elif target_storage_format == 'pallet_products':
                # TODO: merge with line 67 ?
                if not package:
                    # moving stock into a pallet of products, result_package might be new
                    result_package = Package.get_package(result_package, create=True).name
        elif package:
            # mark_as_done package without result_package
            pass
        elif products_info:
            # mark_as_done products without package or result_package
            if target_storage_format == 'package':
                # create result_package when packing products without
                # result_package being set
                result_package = Package.create({}).name

        return (result_package, parent_package)

    def get_package_move_lines(self, package):
        """ Extend to get move lines of package when package is
            a parent package and handle swapping packages.
        """
        if package.children_ids:
            res = self.filtered(lambda ml: ml.package_id in package.children_ids)
        else:
            res = super(StockMoveLine, self).get_package_move_lines(package)

        if not res:
            # check if the package can be swapped
            picking = self.mapped('picking_id')
            move_lines = picking._handle_swap(package)

        return res
