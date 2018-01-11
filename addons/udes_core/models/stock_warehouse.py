# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import ValidationError

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    def _prepare_info(self):
        """
            Prepares the following info of the warehouse in self:
            - in_type_id: int
            - out_type_id: int
            - pack_type_id: int
            - pick_type_id: int
            - int_type_id: int
        """
        self.ensure_one()

        return {'in_type_id': self.in_type_id.id,
                'out_type_id': self.out_type_id.id,
                'pack_type_id': self.pack_type_id.id,
                'pick_type_id': self.pick_type_id.id,
                'int_type_id': self.int_type_id.id,
                }

    def get_info(self):
        """ Return a list with the information of each warhouse in self.
        """
        res = []
        for warehouse in self:
            res.append(warehouse._prepare_info())

        return res

    def get_picking_types(self):
        """ Returns a recordset with the picking_types of the warehouse
        """
        PickingType = self.env['stock.picking.type']

        self.ensure_one()
        # get picking types of the warehouse
        picking_types = PickingType.search([('warehouse_id', '=', self.id)])
        if not picking_types:
            raise ValidationError(_('Cannot find picking types for warehouse %s.') % self.name)

        return picking_types
