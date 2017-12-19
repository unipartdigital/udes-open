# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from .main import UdesApi

def transform_id_fields(input_dict, fields):
    for field in fields:
        if field in input_dict and input_dict[field]:
            input_dict[field]=input_dict[field][0]

    return input_dict

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
    'u_pi_count_move_picking_type_id',
    'u_stock_investigation_picking_type_id',
]
WAREHOUSE_OTHER_FILEDS = [
    'u_handle_damages_picking_type_ids',
    'u_print_labels_picking_type_ids',
    'u_pallet_barcode_regex',
    'u_package_barcode_regex',
]
WAREHOUSE_ALL_FIELDS = WAREHOUSE_ID_FILEDS + WAREHOUSE_OTHER_FILEDS

PICKING_TYPE_ID_FIELDS = [
    'default_location_dest_id',
    'default_location_src_id',
]
PICKING_TYPE_OTHER_FIELDS = [
    'id',
    'code',
    'count_picking_backorders',
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
]
PICKING_TYPE_ALL_FIELDS = PICKING_TYPE_ID_FIELDS + PICKING_TYPE_OTHER_FIELDS

class WarehouseStock(UdesApi):

    #@http.route('/api/stock-warehouse/', type='json', methods=['GET'], auth='user')
    @http.route('/api/stock-warehouse/', type='json', auth='user')
    def read_stock_warehouse_config(self):
        """
        Read the stock_warehouse records on the endpoint /api/stock-warhouse/
        :return: the main warehouse configuration + stock picking types values in a json format
        """
        Warehouse = request.env['stock.warehouse']
        PickingType = request.env['stock.picking.type']

        # get the warehouse
        warehouse = Warehouse.get_warehouse()
        # read warehouse data
        warehouse_config_dict = warehouse.read(fields=WAREHOUSE_ALL_FIELDS)[0]
        # transform id fields into ids instead of id+name
        warehouse_config_dict = self.transform_id_fields(warehouse_config_dict, WAREHOUSE_ID_FILEDS)
        # get picking types
        picking_types = PickingType.search_read(fields=PICKING_TYPE_ALL_FIELDS)
        assert len(picking_types) > 1, 'The picking types have not been loaded properly'
        # for each picking type transform id fields into ids instead of id+name
        picking_types = [ self.transform_id_fields(pt, PICKING_TYPE_ID_FIELDS) for pt in picking_types]
        warehouse_config_dict['picking_types'] = picking_types

        return warehouse_config_dict
