# UDES Stock Packaging

## Default settings

- None at present.

## Requires
- package_hierarchy, udes_stock

## Models

### Warehouse (model: stock.warehouse)

Provides warehouse configuration.

| Field Name               | Description             |
|--------------------------|-------------------------|
| u_pallet_barcode_regex   | Default Pallet Barcode  |
| u_package_barcode_regex  | Default Package Barcode |

### Packages (model: stock.quant.package)

Physical packages of products. They can be used to represent parcels sent to customers, a pallet of products sent from a supplier, a tote used to pick products so they can be sent, or any combination of the above.  A package may also contain other packages.

| Helpers  | Description                                                           |
|----------|-----------------------------------------------------------------------|
| create   | Create a package, checking that the pallet name is valid, if provided |
| write    | Update a package, checking that the pallet name is valid, if provided |


### Stock Picking (model: stock.picking)

This is essentially a collection of products that are to be moved from one location to another.

| Helpers                        | Description                                                                                                                                                                                                                                                                                                                                         |
|--------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| prepare_result_packages        | Prepare result packages according to a given target storage format and the parameters provided                                                                                                                                                                                                                                                      |
