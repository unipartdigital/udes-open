# -*- coding: utf-8 -*-

from odoo import api, fields, models

TRANSPORT_FIELDS = ['u_vehicle_sequence', 'u_vehicle_description', 'u_license_plate', 'u_driver_name']


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    u_transport_id = fields.Many2one('udes_transport_management.transport',
                                     'Transport Info',
                                     copy=False,
                                     index=True)
    # related fields to show the transport information
    u_vehicle_sequence = fields.Integer(string='Vehicle Sequence Number',
                                        related='u_transport_id.vehicle_sequence')
    u_vehicle_description = fields.Char(string='Vehicle Description',
                                        related='u_transport_id.vehicle_description')
    u_license_plate = fields.Char(string='Vehicle Registration',
                                  related='u_transport_id.license_plate')
    u_driver_name = fields.Char(string='Driver Name',
                                related='u_transport_id.driver_name')
    u_requires_transport = fields.Boolean(string='Show transport management tab',
                                          related='picking_type_id.u_requires_transport')

    _sql_constraints = [
        ('transport_uniq', 'unique(u_transport_id)', 'Only one transport information is allowed per picking.'),
    ]

    def _create_transport_info_data(self, values):
        """ Create a transport information for each picking that doesn't
            have it.
        """
        # Instantiate Transport object
        Transport = self.env['udes_transport_management.transport']
        # Filter values for transport info and substring the 'u_' from the keys to create correct transport field names
        filtered_transport = dict((k[2:], values[k]) for k in TRANSPORT_FIELDS if k in values)
        # Only create a transport object if transport data exists in values
        if filtered_transport:
            for record in self:
                if not record.u_transport_id:
                    # Add picking_id as this always exists
                    filtered_transport['picking_id'] = record.id
                    # Create the Transport object with created dict
                    Transport.create(filtered_transport)

        return values

    @api.multi
    def write(self, values):
        values = self._create_transport_info_data(values)
        res = super(StockPicking, self).write(values)
        return res

    @api.model
    def create(self, values):
        res = super(StockPicking, self).create(values)
        res._create_transport_info_data(values)
        return res

    @api.multi
    def _prepare_info(self, priorities=None, fields_to_fetch=None, **kwargs):
        data = super(StockPicking, self)._prepare_info(priorities=priorities, fields_to_fetch=fields_to_fetch, **kwargs)
        # If the stock picking requires transport
        if self.u_requires_transport and (not fields_to_fetch or 'u_transport_id' in fields_to_fetch):
            # Get transport info and add it to data
            transport_dict = {}
            for field in TRANSPORT_FIELDS:
                value = getattr(self, field, False)
                # If sequence number is 0, it will evaluate to false here
                if value:
                    transport_dict[field] = value
            data['u_transport_id'] = transport_dict
        return data
