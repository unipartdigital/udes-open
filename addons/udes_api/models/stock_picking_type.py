# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .common import transform_id_fields

PICKING_TYPE_ID_FIELDS = [
    'default_location_dest_id',
    'default_location_src_id',
]
PICKING_TYPE_OTHER_FIELDS = [
    'id',
    'code',
    'count_picking_ready',
    'display_name',
    'name', 
    'sequence',
    'u_allow_swapping_packages',
    'u_skip_allowed',
    'u_split_on_drop_off_picked',
    'u_suggest_qty',
    'u_over_receive',
    'u_validate_real_time',
    'u_target_storage_format',
    'u_user_scans',
    'u_enforce_location_dest_id',
]
PICKING_TYPE_ALL_FIELDS = PICKING_TYPE_ID_FIELDS + PICKING_TYPE_OTHER_FIELDS


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    @api.multi
    def get_info(self):
        if not self:
            raise ValidationError(_('Cannot find picking types for the user and warehouse.'))

        picking_types = self.read(fields=PICKING_TYPE_ALL_FIELDS)
        # for each picking type transform id fields into ids instead of id+name
        picking_types = [transform_id_fields(pt, PICKING_TYPE_ID_FIELDS) for pt in picking_types]
        return picking_types
