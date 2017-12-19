# -*- coding: utf-8 -*-

from odoo import models, fields
from .common import transform_id_fields

WAREHOUSE_ID_FILEDS = [
    'in_type_id',
    'out_type_id',
    'pack_type_id',
    'pick_type_id',
    'int_type_id',
    'u_missing_stock_location_id',
    'u_damaged_location_id',
    'u_temp_dangerous_location_id',
    'u_probres_location_id',
    'u_incomplete_location_id',
    'u_dangerous_location_id',
]
WAREHOUSE_OTHER_FILEDS = [
    'u_handle_damages_picking_type_ids',
    'u_print_labels_picking_type_ids',
    'u_pallet_barcode_regex',
    'u_package_barcode_regex',
]
WAREHOUSE_ALL_FIELDS = WAREHOUSE_ID_FILEDS + WAREHOUSE_OTHER_FILEDS

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    def get_info(self):
        self.ensure_one()
        # read warehouse data
        warehouse_config_dict = self.read(fields=WAREHOUSE_ALL_FIELDS)[0]
        # transform id fields into ids instead of id+name
        warehouse_config_dict = transform_id_fields(warehouse_config_dict, WAREHOUSE_ID_FILEDS)

        return warehouse_config_dict

