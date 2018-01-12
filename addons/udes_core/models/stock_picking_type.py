# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import ValidationError

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    def _prepare_info(self):
        """
            Prepares the following info of the picking_type in self:
            - id: int
            - code: string
            - count_picking_ready: int
            - display_name: string
            - name: string
            - sequence: int
            - default_location_dest_id: int
            - default_location_src_id: int
        """
        self.ensure_one()

        return {'id': self.id,
                'code': self.code,
                'count_picking_ready': self.count_picking_ready,
                'display_name': self.display_name,
                'name': self.name,
                'sequence': self.sequence,
                'default_location_dest_id': self.default_location_dest_id.id,
                'default_location_src_id': self.default_location_src_id.id,
                }


    def get_info(self):
        """ Return a list with the information of each picking_type in self.
        """
        res = []
        for picking_type in self:
            res.append(picking_type._prepare_info())

        return res

    def get_picking_type(self, picking_type_id):
        """ Get picking_type from id
        """
        picking_type = self.browse(picking_type_id)
        if not picking_type.exists():
            raise ValidationError(
                    _('Cannot find picking type with id %s') %
                    picking_type_id)
        return picking_type
