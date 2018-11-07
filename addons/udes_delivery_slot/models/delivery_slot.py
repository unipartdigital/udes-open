# -*- coding: utf-8 -*-

from odoo import api, fields, models

import datetime
import math
from odoo.tools.float_utils import float_round


def float_to_time(float_hour):
    """Taken from the 'resource' module to avoid extra dependency"""
    if float_hour == 24.0:
        return datetime.time.max
    return datetime.time(int(math.modf(float_hour)[1]),
                         int(float_round(60 * math.modf(float_hour)[0], precision_digits=0)), 0)


class DeliveryTimeSlot(models.Model):
    """
    Hold the start and end times for a delivery window.
    Note the start and end fields must be displayed using the float_time widget
    in views (ir.qweb.field.float_time) to appear as times.
    """
    _name = 'udes.delivery.slot'

    name = fields.Char("Name")
    ref = fields.Char("Slot Reference", required=True, index=True)
    start_time = fields.Float("Delivery Window Start", required=True,
                         help='Holds a time, as a float number of hours')
    end_time = fields.Float("Delivery Window End", required=True,
                         help='Holds a time, as a float number of hours')
    active = fields.Boolean(string="Active", default=True,
                            track_visibility='onchange')

    _sql_constraints = [
        ('positive_start', 'CHECK(start_time>=0)', 'Start must be 0 or greater'),
        ('positive_duration', 'CHECK(start_time<end_time)', 'End must be after start'),
        ('same_day', 'CHECK((start_time<24) AND (end_time<=24))', 'Times must be 24 hours or less.'),
    ]

    @api.multi
    def as_time(self):
        """Helper to return the start and end time of a record as python
        datetime.time() objects"""
        self.ensure_one()
        return (float_to_time(self.start_time), float_to_time(self.end_time))
