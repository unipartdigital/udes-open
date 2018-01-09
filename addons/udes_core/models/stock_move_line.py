# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.multi
    def validate(self, location_dest_id=None, result_package_id=None, result_package_barcode=None):

        Location = self.env['stock.location']
        Package = self.env['stock.quant.package']

        values = {}

        location = None
        if location_dest_id:
            # get the location to check if it is valid
            location = Location.get_location(location_dest_id)
            values['location_dest_id'] = location.id
        result_package = None
        if result_package_id or result_package_barcode:
            # get the package to check if it is valid
            result_package = Package.get_package(result_package_id or result_package_barcode)
            values['result_package_id'] = result_package.id

        for move_line in self:
            move_values = values.copy()
            move_values['qty_done'] = move_line.product_qty
            if result_package and move_line.result_package_id and result_package != move_line.result_package_id:
                raise ValidationError(
                        _('A container (%s) already exists for the operation'
                          ' but you are using another one (%s)' %
                          (move_line.result_package_id.name, result_package.name)))
            move_line.write(move_values)

 
