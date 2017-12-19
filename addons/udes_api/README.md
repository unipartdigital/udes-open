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

## Quants (model: stock.quant)

Physical instances of products at a location are modelled as quants. Short of "quantitis of stock", these are used to record stock levels are various parts of the warehouse. Using the analogy of object-orientated programming, products = classes, quants = objects.

| Field Name  | Type          | Description |
| ----------- | ------------- | ----------- |
| id | int | |
| package_id | stock.quant.package | (see representation of the packages below) |
| product_id | product.product | (see representation of the products above) |
| quantity | float | The physical quantity of the stock |
| reserved_quantity | float | The number of this quantity that has been reserved |

## Packages (model: stock.quant.package)

Physical packages of products. They can be used to represent parcels sent to customers, a pallet of products sent from a supplier, a tote used to pick products so they can be sent, or any combination of the above.


| Field Name       | Type    | Description                                              |
| ---------------- | ------- | -------------------------------------------------------- |
| id               | int     | |
| name             | string  | |

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
| picking_type_id |  int | See below |

## Picking Type (model: stock.picking.type)

The type of stock.picking can is defined by this type. It can represent a goods in, a putaway, an internal transfer, a pick, a goods out, or any other collection of stock moves the warehouse operators want to model within UDES.

A lot of custom UDES functionality is specfied at the picking type level. This is where the stock storage format is specified, so the system knows how to store stock (i.e. as just products, in packages or pallets).

| Field Name                | Type    | Description                                       |
| ------------------------- | ------- | ------------------------------------------------- |
| id                        | int     | |
| code                      | string  | |
| count_picking_ready       | int     | |
| default_location_dest_id  | int     | |
| default_location_src_id   | int     | |
| display_name              | string  | |
| name                      | string  | |
| sequence                  | int     | Used for ordering picking types in a display. |
| u_allow_swapping_packages | boolean | During a specified pick, this field determines whether we can we swap one package for another if they contain exactly the same. |
| u_skip_allowed            | boolean | Is the user allowed to skip to the next item to pick? |
| u_split_on_drop_off       | boolean | |
| u_suggest_qty             | boolean | Do we display the suggested quantity, or get the user to enter it without any vision of what is expected. When we suggest it, the risk is that users will be automatically confirming it without a thorough check. |
| u_over_receive            | boolean | Is the system able to receive more than is expected. |
| u_target_storage_format   | string  | This defines how the stock is stored at the end of the stock.picking. |
| u_user_scans              | string  | This defines what the user will scan. |
| u_validate_real_time      | boolean | Do we validate move lines in real time |
| u_enforce_location_dest_id| boolean | If the destination location on validation has to excatly match with the location_dest_id of the move lines |

  
## Stock Move

A move of an item of stock from one location to another.

 "move_lines" [{stock.move},]:
      picking.pack_operation_ids._list_data(
          filters['stock_pack_operations'] if 'stock_pack_operations' in


## Stock Move Line


## Stock Warehouse


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
  'u_handle_damages_picking_type_ids': [int],
  'u_print_labels_picking_type_ids': [int],
  'in_type_id': int,
  'out_type_id': int,
  'pack_type_id': int,
  'pick_type_id': int,
  'int_type_id': int,
  'u_missing_stock_location_id': int,
  'u_damaged_location_id': int,
  'u_temp_dangerous_location_id': int,
  'u_probres_location_id': int,
  'u_incomplete_location_id': int,
  'u_dangerous_location_id',
  'u_package_barcode_regex:' string,
  'u_pallet_barcode_regex': string,
  'picking_types': [{picking_type}]
}
```

## Stock Picking

```
URI: /api/stock-picking
HTTP Method: GET
Old method: search_pickings
```
Search for pickings by various criteria and return an array of stock.picking objects that match a given criteria.

* @param (optional) origin - search for stock.picking records based on the origin field. Needs to be a complete match.
* @param (optional) package_barcode - search of stock.pickings associated with a specific package_barcode (exact match). N.B. in the old method, this was pallet.
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
* (PLEASE UPDATE WITH ACCEPTABLE OPTIONS FOR STATES) @param states: A List of strings that are states for pickings.
                       If present only pickings in the states present in the
                       list are returned.
                       Defaults to all
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
* @param (NO LONGER USED - REMOVE) (optional)  use_list_data: Decides whether the _list_data function is used
                        when returning data



Output format:


```javascript
{
  "id": int,
  "name": string,
  "priority": int,
  "backorder_id": int,
  "priority_name": string,
  "origin": string,
  "location_dest_id": int,
  "picking_type_id": int,
  "move_lines" [{},]:
      picking.pack_operation_ids._list_data(
          filters['stock_pack_operations'] if 'stock_pack_operations' in


location_dest_id???
location_id


move_lines_ids: [{}]
lot_id, lot_name


"id", "name", "date", "company_id", "scheduled_date", "is_locked", "picking_type_id", "move_type", "printed", "priority", "partner_id", "location_id", "location_dest_id", "owner_id", "create_uid", "write_uid", "create_date", "write_date",





INSERT INTO "stock_move" ("id", "date_expected", "date", "company_id", "procure_method", "scrapped", "picking_type_id", "product_uom", "product_id", "sequence", "state", "location_dest_id", "priority", "group_id", "product_uom_qty", "ordered_qty", "additional", "location_id", "name", "picking_id", "propagate", "create_uid", "write_uid", "create_date", "write_date") VALUES(nextval('stock_move_id_seq'), '2017-12-12 10:17:24', '2017-12-12 10:17:48', 1, 'make_to_stock', false, 5, 1, 30, 10, 'draft', 14, '1', NULL, '4.000', '4.000', false, 8, '[MBi9] Motherboard I9P57', 69, true, 1, 1, (now() at time zone 'UTC'), (now() at time zone 'UTC')) RETURNING id

INSERT INTO "stock_move" ("id", "date_expected", "date", "company_id", "procure_method", "scrapped", "picking_type_id", "product_uom", "product_id", "sequence", "state", "location_dest_id", "priority", "group_id", "product_uom_qty", "ordered_qty", "additional", "location_id", "name", "picking_id", "propagate", "create_uid", "write_uid", "create_date", "write_date") VALUES(nextval('stock_move_id_seq'), '2017-12-12 10:17:31', '2017-12-12 10:17:48', 1, 'make_to_stock', false, 5, 1, 28, 10, 'draft', 14, '1', NULL, '4.000', '4.000', false, 8, '[C-Case] Computer Case', 69, true, 1, 1, (now() at time zone 'UTC'), (now() at time zone 'UTC')) RETURNING id

UPDATE "stock_picking" SET "activity_date_deadline"=NULL,"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (69)

UPDATE "stock_picking" SET "priority"='1',"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (69)

UPDATE "stock_picking" SET "scheduled_date"='2017-12-12 10:17:24',"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (69)

UPDATE "stock_picking" SET "group_id"=NULL,"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (69)

UPDATE "stock_move" SET "reference"='WH/IN/00030',"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (115, 116)

UPDATE "stock_picking" SET "state"='draft',"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (69)

UPDATE "stock_move" SET "product_qty"=4.0,"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (115, 116)

UPDATE "stock_move" SET "scrapped"=false,"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (115, 116)

UPDATE "stock_move" SET "date_expected"='2017-12-12 10:17:24',"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (115, 116)

UPDATE "stock_move" SET "priority"='1',"write_uid"=1,"write_date"=(now() at time zone 'UTC') WHERE id IN (115, 116)






```
URI: /api/stock-picking
HTTP Method: POST
Old method: create_transfer/create_internal_transfer
```


```
URI: /api/stock-location
HTTP Method: GET
Params:
* @param: id (optional)
```
{
  id: int,
  name: string,
  barcode: string,
  u_blocked: boolean,
  u_blocked_reason: string,
  quant_ids: [
    {
      id: int,
      package_id: {stock.quant.package},
      product_id: {product.product},
      quantity: float,
      reserved_quantity: float
    }] 
}
```
URI: /api/stock-quant-package
HTTP Method: GET
Params:
```

Old methods that can be used: get_quants_from_barcode

```
