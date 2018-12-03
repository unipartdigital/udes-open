# Unipart Digital Enterprise System

UDES aims to provide an open source ERP solution that is capable of handling the demands of industry 4.0. The current focus of the team is on enterprise level inventory, warehousing and logistics solutions.

The core team has strong experience in logistics, business systems, computer science research and user experience. The current implementation is built around the Odoo Community Edition.

## Features of this module

This core module adds the following features to Odoo Community Edition:

* Ability to navigate from one picking to the next using the routes. Using the 3 stage outbound route, the Pick will have a link to the Pack then the Delivery Order.
* Disabled translations on location names.
* Disabled translations on product names.
* Ability to track the visibility of archiving locations.
* Ability to track the visibility of archiving products.
* Ability to search by source package at stock.picking list.
* Ability to search by destination package at stock.picking list.

# Core Data Models

The following models are used extensively throughout UDES, and it is important to understand how they all fit together before embarking on any UDES development work.

## Products (model: product.product)

Products are the actual items we want to handle. These can be car parts, mobile phones or plant pots.

| Field Name   | Type   | Description                                              |
| ------------ | ------ | -------------------------------------------------------- |
| id           | int    | |
| barcode      | string | |
| display_name | string | A formatted, user-friendly representation of the product |
| name         | string | |
| tracking     | string | How the product is tracked in the system. This is used for serial numbers and lots. |

## Locations (model: stock.location)

The warehouse is made up of various locations for storing stock. There are two main types of locations - stock, and non-stock locations. Stock typically represents all the warehouse storage of products that can be sent to customers. The other locations typically represent transition stages around receiving goods and sending goods out to customers.

| Field Name       | Type    | Description                                              |
| ---------------- | ------- | -------------------------------------------------------- |
| id               | int     | |
| barcode          | string  | |
| name             | string  | |
| u_blocked        | boolean | Whether the location has been blocked. If it has been blocked, stock should not be moved to/from this location. |
| u_blocked_reason | string  | A descriptive reason why the location has been blocked. |
| quant_ids | [{stock.quants}]  | A list of all the quants at the given location. |

## Quants (model: stock.quant)

Physical instances of products at a location are modelled as quants. Short of "quantitis of stock", these are used to record stock levels are various parts of the warehouse. Using the analogy of object-orientated programming, products = classes, quants = objects.

| Field Name  | Type          | Description |
| ----------- | ------------- | ----------- |
| id | int | |
| package_id | stock.quant.package | (see representation of the packages below) |
| product_id | product.product | (see representation of the products above) |
| location_id | stock.location | (See representation of the location above) |
| quantity | float | The physical quantity of the stock |
| reserved_quantity | float | The number of this quantity that has been reserved |

## Packages (model: stock.quant.package)

Physical packages of products. They can be used to represent parcels sent to customers, a pallet of products sent from a supplier, a tote used to pick products so they can be sent, or any combination of the above.


| Field Name       | Type    | Description                                              |
| ---------------- | ------- | -------------------------------------------------------- |
| id               | int     | |
| name             | string  | |
| package_id       | int     | ID of the parent package if it exists |
| children_ids     | [{stock.quant.package}] | Children packages information if there is any |
| quant_ids           | [{stock.quant}] | Stock inside the package |

## Stock Picking (model: stock.picking)

This is essentially a collection of products that are to be moved from one location to another.

| Field Name       | Type    | Description                                              |
| ---------------- | ------- | -------------------------------------------------------- |
| id               | int     | |
| name             | string  | |
| priority         | int | |
| backorder_id     | int | If this shipment is split, this refers to the stock.picking that has already been processed. For example, if we are expecting 10 items in stock.picking 1, but only process 6 then try to validate the stock.picking, we will be asked to create a backorder of the remaining 4 in the picking (stock.picking.id = 1), the new picking (i.e. stock.picking.id = 2) with have backorder_id = 1, to refer to the previous 6 that were processed. |
| priority_name    | string | Computed field, used by the API. |
| origin           | string | Typically used as a text reference of where the stock.picking came from. During goods in, this is the ASN (advanced ship notice - the supplier's delivery reference) |
| location_dest_id | int | ID of the stock.location where the stock needs to move to |
| picking_type_id  |  int | See below |
| move_lines       | [{stock.move}] | The stock moves associated with this move. |
| state            | string | State of the picking: 'draft', 'waiting', 'confirmed', 'assigned', 'done', 'cancel'. |
| u_pending        | boolean | If the picking has preceeding work still pending. Only included if picking.type.u_handle_partials==False |

## Picking Type (model: stock.picking.type)

The type of stock.picking can is defined by this type. It can represent a goods in, a putaway, an internal transfer, a pick, a goods out, or any other collection of stock moves the warehouse operators want to model within UDES.

A lot of custom UDES functionality is specfied at the picking type level. This is where the stock storage format is specified, so the system knows how to store stock (i.e. as just products, in packages or pallets).

| Field Name                 | Type    | Description                                       |
| -------------------------- | ------- | ------------------------------------------------- |
| id                         | int     | |
| code                       | string  | |
| count_picking_ready        | int     | |
| default_location_dest_id   | int     | |
| default_location_src_id    | int     | |
| display_name               | string  | |
| name                       | string  | |
| sequence                   | int     | Used for ordering picking types in a display. |
| u_allow_swapping_packages  | boolean | During a specified pick, this field determines whether we can we swap one package for another if they contain exactly the same. |
| u_skip_allowed             | boolean | Is the user allowed to skip to the next item to pick? |
| u_split_on_drop_off        | boolean | |
| u_suggest_qty              | boolean | Do we display the suggested quantity, or get the user to enter it without any vision of what is expected. When we suggest it, the risk is that users will be automatically confirming it without a thorough check. |
| u_over_receive             | boolean | Is the system able to receive more than is expected. |
| u_target_storage_format    | string  | This defines how the stock is stored at the end of the stock.picking (enum: 'pallet_products', 'pallet_packages', 'package', 'product'). |
| u_user_scans               | string  | This defines what the user will scan (enum: 'pallet', 'package', 'product'). |
| u_validate_real_time       | boolean | Do we validate move lines in real time. |
| u_drop_location_constraint | string  | Whether drop location should be scanned, suggested and, then, enforced (enum: 'dont_scan', 'scan', 'enforce', 'suggest'); default: 'scan'. |
| u_drop_location_policy     | string  | To indicate the policy for suggesting drop locations (enum: 'exactly_match_move_line', 'by_products', 'by_packages'); default: 'exactly_match_move_line'. |
| u_drop_location_preprocess  | boolean | Selects if suggestions u_drop_location_policy should be added on assignment. If this is set will apply the u_drop_location_policy and the first location is set as location_dest_id for the set of move_lines. This can only be used with polcies decorated with allow_preprocess, usage on other polcies will result in an ValidationError.|
| u_display_summary          | string  | How to display the Source Document and a summary of all Package Names associated with that Source Document number at Goods-Out (enum: 'none', 'list', 'list_contents'). |
| u_handle_partials          | boolean | If the picking type is allowed to handle partially available pickings. If True, then pickings of this type will report their u_pending value. |
| u_create_procurement_group | boolean | Indicate if a procurement group should be created on confirmation of the picking if one does not already exist. |

More on the enumeration fields below.

`u_drop_location_constraint`:
 - `dont_scan`: don't require scanning the destination location;
 - `scan` (default): the system will require scanning the destination location and it will validate it by checking if it's a child of the pick parent destination location;
 - `suggest`: before require scanning (as per above 'scan'), the system will suggest one or more locations for dropping (NB: such list may be empty; in that case, nothing will be displayed);
 - `enforce`: as 'suggest', but the system will require (by validating the scanned location barcode) dropping in one of the suggested locations (NB: if the list is empty, any child of the pick parent destination location would be valid).

`u_drop_location_policy`:
 - `exactly_match_move_line`: the system will suggest the location that is already expected for the move line;
 - `by_products`: the system will suggest locations by aiming to group together the same products;
 - `by_packages`: the system will suggest locations by aiming to group together the packages.

## Stock Move (model: stock.move)

A move of an item of stock from one location to another.

| Field Name       | Type     | Description                                       |
| ---------------- | -------- | ------------------------------------------------- |
| id               | int      | |
| location_dest_id | {id: stock.location.id, name: stock.location.name, stock.location.barcode} | Cut down location summary, for the destination location |
| location_id      | As above | Source location |
| ordered_qty      | float    | Ordered quantity |
| product_id       | {product.product} | Product summary |
| product_qty      | float    | Real quantity expected |
| quantity_done    | float    | Quantity received so far |
| move_line_ids    | [{stock.move.line}] | The lines associated with this move |

## Stock Move Line (model: stock.move.line)

A move of a specific, handleable item of stock - such as 5 phones, or 1 car door.

| Field Name                 | Type     | Description                                       |
| -------------------------- | -------- | ------------------------------------------------- |
| id                         | int      | |
| create_date                | datetime | |
| location_dest_id           | {id: stock.location.id, name: stock.location.name, stock.location.barcode} | Cut down location summary, for the destination location |
| location_id                | As above | Source location |
| lot_id                     | ???      | TBC  |
| package_id                 | {stock.quant.package} | Source package |
| qty_done                   | float    | |
| product_uom_qty            | float    | Reserved quantity |
| result_package_id          | {stock.quant.package} | Destination package |
| u_result_parent_package_id | {stock.quant.package} | Destination parent package of the result_package_id |
| write_date                 | datetime | |

## Stock Warehouse

Configuration information for the an entire warehouse.

| Field Name                         | Type             | Description                    |
| ---------------------------------- | ---------------- | ------------------------------ |
| u_handle_damages_picking_type_ids  | [int]            | |
| u_print_labels_picking_type_ids    | [int]            | |
| in_type_id                         | int              | |
| out_type_id                        | int              | |
| pack_type_id                       | int              | |
| pick_type_id                       | int              | |
| int_type_id                        | int              | |
| u_missing_stock_location_id        | int              | |
| u_damaged_location_id              | int              | |
| u_temp_dangerous_location_id       | int              | |
| u_probres_location_id              | int              | |
| u_incomplete_location_id           | int              | |
| u_dangerous_location_id            | int              | |
| u_package_barcode_regex            | string           | |
| u_pallet_barcode_regex             | string           | |
| u_pi_count_move_picking_type       | string           | |
| u_stock_investigation_picking_type | string           | |

## Picking Batches (model: stock.picking.batch)

Group of pickings to be completed by a user.

| Field Name  | Type          | Description |
| ----------- | ------------- | ----------- |
| id | int | |
| picking_ids | [stock.picking] | List of stock.picking objects|


# API End Points

## Stock Warehouse

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
  'stock_warehouse': {stock.warehouse},
  'picking_types': [{picking_type}]
}
```

## Stock Picking


### Get stock pickings
```
URI: /api/stock-picking
HTTP Method: GET
Old method: search_pickings
```
Search for pickings by various criteria and return an array of stock.picking objects that match a given criteria.

* @param (optional) origin - search for stock.picking records based on the origin field. Needs to be a complete match.
* @param (optional) package_name - search of stock.pickings associated with a specific package_name (exact match). N.B. in the old method, this was pallet.
* @param (optional) product_id - is set then location_id must also be set and stock.pickings are found using both of those values (states is optional).
* @param (optional) location_id is set then only internal transfers acting on that location are considered.
        In all cases, if states is set then only pickings in those states are
        considered.
* @param (optional) backorder_id: id of the backorder picking.
                       If present, pickings are found by backorder_id and states.

* (IGNORE FOR NOW) @param (optional) allops: Boolean. (default=True). If True, all pack operations are included.
                       If False, only pack operations that are for the pallet
                       identified by param pallet (and it's sub-packages) are
                       included.
* @param states: A List of strings that are states for pickings.
                       If present only pickings in the states present in the
                       list are returned.
                       Defaults to all, possible values: 'draft', 'cancel', 'waiting', 'confirmed', 'assigned', 'done'

* @param (optional) result_package_id: If an id is supplied all pickings that are
                        registered to this package id will be returned.
                        This can also be used in conjunction with the states
                        parameter
* @param (optional) picking_priorities: When supplied all pickings of set priorities
                        and :states will be searched and returned
* @param (optional) picking_ids: When supplied pickings of the supplied picking ids
                        will be searched and returned.
                        If used in conjunction with priorities then only those
                        pickings of those ids will be returned.
* @param (optional) bulky (Boolean): This is used in conjunction with the picking_priorities
                        parameter to return pickings that have bulky items
* @param (NO LONGER USED - REMOVE) (optional)  use_list_data: Decides whether the _list_data function is used when returning data

* @param (optional) fields_to_fetch: Array (string). Subset of the default fields to return.

* @param (optional) picking_type_ids: Array (int) If it is set the pickings returned will be only from the picking types in the array.


Output format:


Example getting a new goods-in stock picking expecting to receive 2 products and 5 units each:
```javascript
{ "jsonrpc": "2.0", "result": [{"backorder_id": false, "picking_type_id": 2, "origin": "ASN007", "priority_name": "Normal", "name": "WH/IN/00038", "id": 66, "moves_lines": [{"product_id": {"id": 46, "display_name": "[test01] test01", "name": "[test01] test01", "tracking": "none", "barcode": "test01"}, "ordered_qty": 5.0, "quantity_done": 0.0, "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "product_qty": 5.0, "id": 226, "moves_line_ids": [{"write_date": "2018-02-08 13:32:09", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 186, "package_id": false, "create_date": "2018-02-08 13:32:09", "result_package_id": false, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 0.0}], "location_dest_id": {"barcode": false, "name": "Input", "id": 12}}, {"product_id": {"id": 49, "display_name": "[test03] test03", "name": "[test03] test03", "tracking": "none", "barcode": "test03"}, "ordered_qty": 5.0, "quantity_done": 0.0, "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "product_qty": 5.0, "id": 227, "moves_line_ids": [{"write_date": "2018-02-08 13:32:09", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 187, "package_id": false, "create_date": "2018-02-08 13:32:09", "result_package_id": false, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 0.0}], "location_dest_id": {"barcode": false, "name": "Input", "id": 12}}], "state": "assigned", "priority": "1", "location_dest_id": 12}]}
```

Same picking after packing 1 unit of each product inside packages and inside pallet:
```javascript
{"jsonrpc": "2.0", "result": [{"backorder_id": false, "picking_type_id": 2, "origin": "ASN007", "priority_name": "Normal", "name": "WH/IN/00038", "id": 66, "moves_lines": [{"product_id": {"id": 46, "display_name": "[test01] test01", "name": "[test01] test01", "tracking": "none", "barcode": "test01"}, "ordered_qty": 5.0, "quantity_done": 5.0, "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "product_qty": 5.0, "id": 226, "moves_line_ids": [{"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:58", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 186, "package_id": false, "create_date": "2018-02-08 13:32:09", "result_package_id": {"name": "PACK0000112", "id": 125}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}, {"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:57", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 194, "package_id": false, "create_date": "2018-02-08 13:41:57", "result_package_id": {"name": "PACK0000111", "id": 124}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}, {"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:57", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 192, "package_id": false, "create_date": "2018-02-08 13:41:57", "result_package_id": {"name": "PACK0000110", "id": 123}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}, {"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:56", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 190, "package_id": false, "create_date": "2018-02-08 13:41:56", "result_package_id": {"name": "PACK0000109", "id": 122}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}, {"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:54", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 188, "package_id": false, "create_date": "2018-02-08 13:41:54", "result_package_id": {"name": "PACK0000108", "id": 121}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}], "location_dest_id": {"barcode": false, "name": "Input", "id": 12}}, {"product_id": {"id": 49, "display_name": "[test03] test03", "name": "[test03] test03", "tracking": "none", "barcode": "test03"}, "ordered_qty": 5.0, "quantity_done": 5.0, "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "product_qty": 5.0, "id": 227, "moves_line_ids": [{"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:58", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 187, "package_id": false, "create_date": "2018-02-08 13:32:09", "result_package_id": {"name": "PACK0000112", "id": 125}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}, {"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:57", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 195, "package_id": false, "create_date": "2018-02-08 13:41:57", "result_package_id": {"name": "PACK0000111", "id": 124}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}, {"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:57", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 193, "package_id": false, "create_date": "2018-02-08 13:41:57", "result_package_id": {"name": "PACK0000110", "id": 123}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}, {"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:56", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 191, "package_id": false, "create_date": "2018-02-08 13:41:56", "result_package_id": {"name": "PACK0000109", "id": 122}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}, {"u_result_parent_package_id": {"name": "PAL00001", "id": 120}, "write_date": "2018-02-08 13:41:54", "location_id": {"barcode": false, "name": "Vendors", "id": 8}, "id": 189, "package_id": false, "create_date": "2018-02-08 13:41:54", "result_package_id": {"name": "PACK0000108", "id": 121}, "location_dest_id": {"barcode": false, "name": "Input", "id": 12}, "qty_done": 1.0}], "location_dest_id": {"barcode": false, "name": "Input", "id": 12}}], "state": "assigned", "priority": "1", "location_dest_id": 12}]}

```


### Create stock picking
```
URI: /api/stock-picking
HTTP Method: POST
Old method: create_transfer/create_internal_transfer
```

Creates a transfer and stock moves for a given list of stock.quant ids

* @param quant_ids - list of quant ids to create stock.moves for the transfer
* @param location_id - location from where we create the transfer
* @param picking_type_id: int The type of the stock.picking.
* @param quant_ids: Array (int) An array of the quants ID to add to the stock.picking
* @param location_id: int ID of the location where the stock.picking is moving from.
* @param location_dest_id: int ID of the location where the stock is going to be moved to.
* @param result_package_id: int The target package ID
* @param move_parent_package: Boolean (default false) Used in pallets/nested packages, to maintain the move of the entire pallet.
* @return: the stock.picking in the same format as the GET API method.


### Update stock picking
```
URI: /api/stock-picking/:id
HTTP Method: POST
Old method(s): force_validate, validate_operation, confirm_transfer
```

Update/mutate the stock picking

* @param id - the id of the stock.picking to process.
* @param (optional) quant_ids: as POST
* @param (optional) move_parent_package: as POST
* @param (optional) force_validate - forces the transfer to be completed. Depends on parameters
* @param (optional) validate - Validate the transfer unless there are move lines todo, in that case it will raise an error.
* @param (optional) create_backorder - When true, allows to validate a transfer with move lines todo by creating a backorder.
* @param (optional) location_dest_id - target destination
* @param (optional) location_dest_name - target destination
* @param (optional) location_dest_barcode - target destination
* @param (optional) result_package_name - If it corresponds to an existing package/pallet that is not in an other location, we will set it to the `result_package_id` of the operations of the picking (i.e. transfer). If the target storage format of the picking type is pallet of packages it will set `result_parent_package_id`.
* @param (optional) package_name - Name of the package of the picking that has been effectively scanned, to be marked as done.
* @param (optional) expected_package_name - Name of the package that was expected to be scanned as part of the picking, to be swapped with the `package_name`.
* @param (optional) product_ids - An array with the products information to be marked as done, where each dictionary contains: barcode, qty and lot numbers if needed
* @param (optional) u_transport_id - A dictionary of transport information to update the stock picking with

Api call example to mark as done one unit of product test01 from picking with id 60.
If the target storage format of the picking type is pallet of packages, test01 move line will have as `result_package_id` a new package and as `result_parent_package_id` the package with name PAL007. If the target storage format of the picking type is pallet of products, test01 move line will have as `result_package_id` the package with name PAL007.
```javascript
odoo.__DEBUG__.services['web.ajax'].jsonRpc('/api/stock-picking/60', 'call', {
    products_info: [{'product_barcode': 'test01', 'qty': 1}],
    result_package_name: 'PAL007',
}).then(function(result){console.log(result); } )
```

Api call example to mark as done two units of serial numbered product test02 from picking with id 60:
```javascript
odoo.__DEBUG__.services['web.ajax'].jsonRpc('/api/stock-picking/60', 'call', {
    products_info: [{'product_barcode': 'test02', 'qty': 2, serial_numbers: ['sn0001','sn0002']}],
}).then(function(result){console.log(result); } )
```

### Package is compatible with stock picking
```
URI: /api/stock-picking/:id/is_compatible_package/:package_name
HTTP Method: GET
```

Check that a package is not in use and hence is compatible with the stock picking, i.e., the package does not exist, it is not in stock and the package it has not been used in any other picking.

* @param id - the id of the stock.picking to check.
* @param package_name - string with the name of the package.

### Retrieve the list of suggested locations for a given package or move lines

```
URI: /api/stock-picking/:id/suggested-locations
HTTP Method: GET
```
Suggest drop off locations based on the configured `u_drop_location_policy`.

* `id` - the id of the stock.picking that is being processed.

Request payload - json object:

* `move_line_ids`: list of the move line ids being processed.

Response payload - json array with Location objects; exmple:

```javascript
{ "jsonrpc": "2.0",
  "result" : [
    {"id": 1, "name": "Location 1", "barcode": "L00000100"},
    {"id": 2, "name": "Location 2", "barcode": "L00000200"}
]}
```

## Stock Location

### Stock Location
```
URI: /api/stock-location
HTTP Method: GET
Params:
@param load_quants - (optional, default = false) Load the quants associated with a location.
@param location_id - (optional) the location's id
@param location_name - (optional) this is a string that entirely matches the name
@param location_barcode - (optional) this is a string that entirely matches the barcode
@param check_blocked - (optional, default = false) When enabled, checks if the location is blocked, in which case an error will be raise.
@return stock.location (as described above, containing the quants in the format also listed above).
```

### Stock Location PI Count
```
URI: /api/stock-location-pi-count/
Method: POST
Params:
@param pi_request: JSON object with "pi_count_moves", "inventory_adjustments", "preceding_inventory_adjustments" and "location_id" entries
```

Creates inventory adjustments and count moves as specified in the request.
Returns an error in case any of the specified references (locations, packages,
products) is unknown.
Returns `true` in case the request is successfully processed.

The JSON schema for the `pi_request` object can be found
[here](schemas/stock-location-pi-count.json).

### Stock Location Block
```
URI: /api/stock-location/block/
Method: POST
```

@param reason - (String) indicates the reason for blocking the location
@param location_id - (Int - optional) the location id
@param location_name - (String - optional) this is a string that entirely matches the name
@param location_barcode - (String - optional) this is a string that entirely matches the barcode

Marks the specified location as 'blocked'.
Returns an error in case the location is not properly specified (i.e. in case
none of the optional args are given) or if the location is already blocked.
Returns `true` in case of success.

## Packages

```
URI: /api/stock-quant-package
HTTP Method: GET
Old method(s): get_quants_from_barcode
```
Search for a package by id or name and returns a stock.quant.package object that match the given criteria.
If no package can be found then this will return an empty array

* @param package_id - (optional) the package's id
* @param package_name - (optional) this is a string that entirely matches the name
* @param check_reserved - (optional, default = false) When enabled, checks if the package has stock reserved, in which case an error will be raise.

## Products

```
URI: /api/product-product
HTTP Method: GET
Old method(s): ???
```
Search for a product by id, name or barcode and returns a product object that match the given criteria.

* @param product_id - (optional) the product's id
* @param product_name - (optional) this is a string that entirely matches the name
* @param product_barcode - (optional) this is a string that entirely matches the barcode
* @param fields_to_fetch - (optional): Subset of the default returned fields to return

## Stock Picking Batch

### Get picking batch
```
URI: /api/stock-picking-batch
HTTP Method: GET
Old method(s): get_users_wave
```
Search for a picking batch that is `in_progress` and assigned to the requester
user.

Response:

It returns a JSON object with:
 - the `id` and `name` of the batch;
 - `picking_ids`: an array  metadata of the `assigned` pickings of the batch
 - `result_package_names`: an array with the result packages

In case no batch is determined, an empty object is returned.
Returns an error if the user has multiple batches asssigned, regardless of the
picking type.

### Assign picking batch
```
URI: /api/stock-picking-batch/assign/
HTTP Method: POST
```
Assign a `ready` batch of the specified picking type to the current user.
By "assign" we mean that the batch `user_id` will be set to the user ID and the
batch state will be moved to `in_progress`.

Request:

A JSON object containing a single `picking_type_id` numeric entry, indicating
the picking type of the batch that should be assigned.

Response (same as /api/stock-picking-batch GET):

In case the backend succeeds to assign a batch to the current user, the response
will contain a JSON object with the same format as the above `get` endpoint,
that will represent the assigned batch.
Otherwise it will include an empty JSON object.

### Create picking batch
```
URI: /api/stock-picking-batch
HTTP Method: POST
Old method(s): generate_wave_for_user
```
Create a new batch and assign it to the requester user.
The batch will be in the `in_progress` state and will have its `ephemeral`
field flagged. As a consequence of that, the batch pickings will be unlinked
when the user logs out or when the `unassign` endpoint is invoked against such
batch.

Request:

A JSON object containing:

* @param picking_type_id - Id of the picking type for the pickings which will be used to create the batch.
* @param picking_priorities - (optional) List of priorities to search for the pickings

Response (same as /api/stock-picking-batch GET):

In case the backend succeeds to create a batch for the requester user, the
response will contain a JSON object with the same format as the above `get`
endpoint that will represent the new batch. Otherwise it will include an empty
JSON object.

### Unassign picking batch
```
URI: /api/stock-picking-batch/:id/unassign/
HTTP Method: POST
```
Clears the `user_id` field of the batch (specified by ID).
In case the batch is `in_progress`, its state will be set back to `ready`.
In case of "ephemeral" batch, all the included pickings will be unliked (i.e.
their `batch_id` fields will be cleared).

Request:

The request shall not contain any payload; the batch `id` must be given in the
URI.

Response:

Returns true on success otherwise an error indicating the failure (e.g. the
batch was not in the `in_progress` state; the batch was not assigned to the
current user).

### Update picking batch
```
URI: /api/stock-picking-batch/:id
HTTP Method: POST
Old method(s): drop_off_picked
```
Update current user's picking batch.

* @param id - id of the batch to process
* @param location_barcode - (optional) Barcode of the location where the picked stock is dropped off
* @param continue_batch - (optional) Determines if the batch should continue or finish the batch (not used)

### Validate drop off location of picking batch
```
URI: /api/stock-picking-batch/:id/is-valid-dest-location/
HTTP Method: GET
Old method(s): is_valid_location_dest_id
```

* @param id - id of the batch to process
* @param location_id - (optional) id of the drop off location to be validated
* @param location_name - (optional) name of the drop off location to be validated
* @param location_barcode - (optional) barcode of the drop off location to be validated

One of [`location_id`, `location_name`, `location_barcode`] must
be specified in the request.

Response: contains a boolean, indicating whether the location specified in the
request can be used for the drop off.

### Create unpickable item
```
URI: /api/stock-picking-batch/:id/unpickable
HTTP Method: POST
Old method(s): unpickable_item
```
* @param id - id of the batch to mark as having an unpickable move line
* @param reason - string (enum - see values below) describing the reason that this move line is unpickable
* @param product_id - (optional) id of the product that is unpickable
* @param location_id - (optional) id of the loction of the unpickable product
* @param package_name - string (optional) name of the unpickable package or package name where the product should have been picked
* @param lot_name - string (optional) serial number of the unpickable product

For the given batch id (`id` of the URL path) and request payload, the backend
will generate a stock investigation picking for the related stock move lines if
required by the specified reason. In turn, this will create a backorder if
necessary (refer to implementation).

Values of the `reason` enumeration type:
 - `part missing`
 - `damaged part`
 - `details on package incorrect`
 - `no suggested location`
 - `package does not fit`
 - `location cannot be used`

Returns `true` in case of success.

### Get next task to pick
```
URI: /api/stock-picking-batch/:id/next
HTTP Method: POST
Old method(s): none
```
* @param id - id of the batch to get next task to pick
* @param skipped_product_ids - (optional) list of product ids that should be skipped by next

Returns the information of the next task to pick: picking_id and quant_id or package_id.

### Check whether the user has any assigned batch
```
URI: /api/stock-picking-batch/check-user-batches
HTTP Method: GET
```
Returns `true` if the user has any assigned batch, `false` otherwise.
Does not check whether the user has multiple batches assigned.

## Stock Picking Priorities
```
URI: /api/stock-picking-priorities/
HTTP Method: GET
Old method(s): get_priority_groups
```
Returns the list of possible groups of priorities with the following format:

```
[{
    name: 'Picking',
    priorities: [
        {'id': 2, 'name': 'Urgent'},
        {'id': 1, 'name': 'Normal'}
        ]
}]
```

## Print

### Set users default printer
```
URI: /api/print-printer/set-user-printer
HTTP Method: POST
Old method(s): set_user_printer
```
Sets users default printer to that with the barcode provided

* @param barcode (string) - barcode of the printer you wish to set as user default

### Print report
```
URI: /api/print-printer/spool-report
HTTP Method: POST
Old method(s): spool_report
```
Prints a report using users default printer.

* @param object_ids Array (int) - the object ids to add to report
* @param report_name (string) - name of the report template
* @param (optional) copies (int, default=1) - the number of copies to print
* @param (optional) kwargs - other data passed to report
