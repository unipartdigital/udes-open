# -*- coding: utf-8 -*-

from odoo import models,  _
from odoo.exceptions import ValidationError

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

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
