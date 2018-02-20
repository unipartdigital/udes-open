# -*- coding: utf-8 -*-

from odoo import api, fields, models

TRAILER_FIELDS = ['u_trailer_num', 'u_trailer_ident', 'u_trailer_license', 'u_trailer_driver']


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
    u_requires_transport = fields.Boolean(string='Show transport management tab',
                                          related='picking_type_id.u_requires_transport')

    _sql_constraints = [
        ('trailer_info_uniq', 'unique(u_trailer_info_id)', 'Only one trailer information is allowed per picking.'),
    ]

    def _create_trailer_info_data(self, values):
        """ Create a trailer information for each picking that doesn't
            have it.
        """
        # Instantiate TrailerInfo object
        TrailerInfo = self.env['udes_transport_management.trailer_info']

        # Filter values for trailer info and substring the 'u_' from the keys to create correct trailer_info field names
        filtered_trailer_info = dict((k[2:], values[k]) for k in TRAILER_FIELDS if k in values)

        # Only create a trailer_info object if trailer_info data exists in values
        if filtered_trailer_info:
            for record in self:
                if not record.u_trailer_info_id:
                    # Add picking_id as this always exists
                    filtered_trailer_info['picking_id'] = record.id

                    # Create the TrailerInfo object with created dict
                    TrailerInfo.create(filtered_trailer_info)

        return values

    @api.multi
    def write(self, values):
        values = self._create_trailer_info_data(values)
        res = super(StockPicking, self).write(values)
        return res

    @api.model
    def create(self, values):
        res = super(StockPicking, self).create(values)
        res._create_trailer_info_data(values)
        return res

    # @api.multi
    # def _prepare_info(self, **kwargs):
    #     data = super(StockPicking, self)._list_data_prepare_info(**kwargs)
    #
    #     #todo   only add to data fields that exist
    #
    #     for field in TRAILER_FIELDS:
    #         value = getattr(self, field, False)
    #         if value:
    #             data[field] = value
    #
    #     return data

