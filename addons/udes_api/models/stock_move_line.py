# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def validate(self, location_dest=None, result_package=None, package=None, products_info=None):
        """ Extend validate function to handle another level of packages and
            use u_target_storage_format.
        """

        move_lines = self

        package, result_package, parent_package = \
                self._prepare_packages(package, result_package, products_info)

        if package:
            # TODO: swap package handling
            #move_lines = self._handle_swap()
            pass

        res = super(StockMoveLine, move_lines).validate(location_dest=location_dest,
                                                  result_package=result_package,
                                                  package=package,
                                                  products_info=products_info)

        if parent_package:
            res.write({'u_result_parent_package_id': parent_package.id})

        return res

    def _prepare_packages(self, package, result_package, products_info):

        Package = self.env['stock.quant.package']

        # atm validate is only called per picking
        picking = self.mapped('picking_id')
        picking.ensure_one()

        target_storage_format = picking.picking_type_id.u_target_storage_format

        parent_package = None
        # error when trying to validate a full package or setting result package
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
                       raise ValidationError(_('Some of the move lines does not have result package.'))

            elif target_storage_format == 'pallet_products':
                if not package:
                    # moving stock into a pallet of products, result_package might be new
                    result_package = Package.get_package(result_package, create=True).name
        elif package:
            # validate package without result_package
            pass
        elif products_info:
            # validate products without package or result_package
            if target_storage_format == 'package':
                # create result_package when packing products without
                # result_package being set
                result_package = Package.create({}).name

        return (package, result_package, parent_package)


    def get_package_move_lines(self, package):
        """ Extend to get move lines of package when package is
            a parent package.
        """
        if package.children_ids:
            res = self.filtered(lambda ml: ml.package_id in package.children_ids)
        else:
            res = super(StockMoveLine, self).get_package_move_lines(package)

        return res
