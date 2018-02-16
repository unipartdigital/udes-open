# -*- coding: utf-8 -*-

from odoo import api, fields, models

TRAILER_FIELDS = ['u_trailer_num','u_trailer_ident','u_trailer_license', 'u_trailer_driver']

class StockPicking(models.Model):

    _inherit = 'stock.picking'

    u_trailer_info_id = fields.Many2one('udes_transport_management.trailer_info',
                                       'Trailer Info',
                                       copy=False,
                                       index=True)
    # related fields to show the trailer information
    u_trailer_num = fields.Integer(string='Trailer number',
                                   related='u_trailer_info_id.trailer_num')
    u_trailer_ident = fields.Char(string='Trailer unit ID',
                                  related='u_trailer_info_id.trailer_ident')
    u_trailer_license = fields.Char(string='Vehicle registration',
                                    related='u_trailer_info_id.trailer_license')
    u_trailer_driver = fields.Char(string='Driver name',
                                   related='u_trailer_info_id.trailer_driver')

    _sql_constraints = [
        ('trailer_info_uniq', 'unique(u_trailer_info_id)', 'Only one trailer information is allowed per picking.'),
    ]

    def _create_trailer_info_data(self, values):
        """ Create a trailer information for each picking that doesn't
            have it.
        """
        TrailerInfo = self.env['udes_transport_management.trailer_info']
        if any([x for x in TRAILER_FIELDS if x in values]):
            for record in self:
                if not record.u_trailer_info_id:
                    trailer = TrailerInfo.create({'picking_id': record.id})
        return values

    @api.multi
    def write(self, values):
        values = self._create_trailer_info_data(values)
        res = super(StockPicking, self).write(values)
        return res

    # @api.multi
    # def _list_data_prepare_info(self, filters, priorities):
    #     data = super(StockPicking, self)._list_data_prepare_info(filters, priorities)
    #     for field in TRAILER_FIELDS:
    #         value = getattr(self, field, False)
    #         if value:
    #             data[field] = value
    #     return data
