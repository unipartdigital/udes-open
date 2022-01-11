# -*- coding: utf-8 -*-
from odoo.tools.translate import _
from odoo import api, fields, models


class Transport(models.Model):
    _name = "udes_transport_management.transport"
    _description = "UDES Transport Info"

    vehicle_sequence = fields.Integer(string="Vehicle Sequence Number", required=False, copy=False)
    vehicle_description = fields.Char(string="Vehicle Description", required=False, copy=False)
    license_plate = fields.Char(string="Vehicle Registration", required=False, copy=False)
    driver_name = fields.Char(string="Driver Name", required=False, copy=False)

    picking_id = fields.Many2one("stock.picking", "Transfer", required=True, index=True, copy=False)

    _sql_constraints = [
        (
            "picking_id_uniq",
            "unique(picking_id)",
            "Only one transport information is allowed per picking.",
        )
    ]

    def _update_picking_data(self):
        """ Update u_transport_id of the related picking if
            it is not set at the picking.
        """
        self.ensure_one()
        if not self.picking_id.u_transport_id:
            self.picking_id.u_transport_id = self

    @api.model
    def create(self, values):
        res = super(Transport, self).create(values)
        res._update_picking_data()
        return res

    @api.multi
    def _prepare_info(self, **kwargs):
        # Create a dict of all the fields
        data = {
            "vehicle_sequence": self.vehicle_sequence,
            "vehicle_description": self.vehicle_description,
            "license_plate": self.license_plate,
            "driver_name": self.driver_name,
        }

        return data

    def get_info(self, **kwargs):
        """ Return a list with the information of each picking in self.
        """
        # Create an array of transport records in self, there should only be one
        res = []
        for transport in self:
            res.append(transport._prepare_info(**kwargs))

        return res
