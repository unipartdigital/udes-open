```
URI: /api/stock-warehouse/get
Old method: read_stock_warehouse_config
```
Load the warehouse config for the stock.warehouse associated with the current user account.

If it is simple, filter picking types to only show the ones that the user has permission to view.

IMPORTANT - N.B. migrate code from the sg branch, as one of the fields is only in that branch! 

```javascript
{
  'u_handle_damages_picking_type_ids': [int],
  'u_print_labels_picking_type_ids': [int],
  'in_type_id': int,
  'u_missing_stock_location_id': int,
  'u_damaged_location_id': int,
  'u_temp_dangerous_location_id': int,
  'u_probres_location_id': int,
  'u_incomplete_location_id': int,
  'u_dangerous_location_id',
  'u_package_barcode_regex:' string,
  'u_pallet_barcode_regex': string,
  'picking_types': [{
    'id': int,
    'code': string,
    'count_picking_backorders': int,
    'count_picking_ready': int,
    'default_location_dest_id': int,
    'default_location_src_id': int,
    'display_name': string,
    'name': string, 
    'sequence': int,
    'u_allow_swapping_packages': boolean,
    'u_skip_allowed': boolean,
    'u_split_on_drop_off_picked': boolean,
    'u_suggest_qty': boolean,
    'u_over_receive': boolean,
    'u_target_storage_format': string}
  ]
}
```

```
URI: /api/stock-picking/create
Old method: create_transfer/create_internal_transfer
```

```
URI: /api/stock-picking/search
```

```
URI: /api/stock-location/search
Params:
```

```
URI: /api/stock-quant-package/search
Params:
```

Old methods that can be used: get_quants_from_barcode

```
/api/stock-picking/search
```

```
/api/stock.quant.package/search
```
