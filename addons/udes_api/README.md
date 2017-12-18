```
URI: /api/stock-warehouse
HTTP Method: GET
Old method: read_stock_warehouse_config
```
Load the warehouse config for the stock.warehouse associated with the current user account.

If it is simple, filter picking types to only show the ones that the user has permission to view.

IMPORTANT - N.B. migrate code from the sg branch, as one of the fields is only in that branch! 

Expected output format:

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
URI: /api/stock-picking
HTTP Method: GET
Old method: search_pickings
```
Search for pickings by various criteria and return an array of stock.picking objects that match a given criteria.

@param (optional) picking_id - 
@param (optional) origin - search for stock.picking records based on the origin field. Needs to be a complete match.
@param (optional) package_barcode - search of stock.pickings associated with a specific package_barcode (exact match). N.B. in the old method, this was pallet.
@param (optional) product_id - is set then location_id must also be set and stock.pickings are found using both of those values (states is optional).
@param (optional) location_id is set then only internal transfers acting on that location are considered.

        In all cases, if states is set then only pickings in those states are
        considered.

        :param origin: source document used to find pickings.
                       If present, pickings are found by origin and states.
        :param backorder_id: id of the backorder picking.
                       If present, pickings are found by backorder_id and states.

@param allops: Boolean. (default=True). If True, all pack operations are included.
                       If False, only pack operations that are for the pallet
                       identified by param pallet (and it's sub-packages) are
                       included.
@param states: A List of strings that are states for pickings.
                       If present only pickings in the states present in the
                       list are returned.
                       Defaults to all
        :param result_package_id: If an id is supplied all pickings that are
                        registered to this package id will be returned.
                        This can also be used in conjunction with the states
                        parameter
        :param picking_priorities: When supplied all pickings of set priorities
                        and :states will be searched and returned
        :param picking_ids: When supplied pickings of the supplied picking ids
                        will be searched and returned.
                        If used in conjunction with priorities then only those
                        pickings of those ids will be returned.
        :param bulky (Boolean): This is used in conjunction with the picking_priorities
                        parameter to return pickings that have bulky items
        :param use_list_data: Decides whether the _list_data function is used
                        when returning data
        :rtype: list
        
        
        


```
URI: /api/stock-picking
HTTP Method: POST
Old method: create_transfer/create_internal_transfer
```


```
URI: /api/stock-location
HTTP Method: GET
Params:
```

```
URI: /api/stock-quant-package
HTTP Method: GET
Params:
```

Old methods that can be used: get_quants_from_barcode

```
