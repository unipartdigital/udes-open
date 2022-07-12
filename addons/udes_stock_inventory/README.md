# UDES Stock Inventory
This module contains overrides to the core Odoo functionality for Inventory Adjustments. Currently the changes are
around user experience, the inventory adjustment details are now all held within the same screen. An inventory
adjustment now also requires at least one location to be set.

## Default settings
None

## Requires
- stock:
  This module needs to inherit and add functionality to models from stock
- product:
  Override for `product.product` search is required for restricting product selection on inventory lines
- udes_stock:
  This module is designed to work on top of udes_stock, the core UDES module for stock functionality

## Models

### Inventory (model: stock.inventory)
Make inventory locations required, add computed helper fields used within the form view of adjustments.

| Field Name       | Type    | Description                                                           |
|------------------|---------|-----------------------------------------------------------------------|
| location_ids        | Many2many | Same functionality as Odoo core, except it is now required for at least one location to be set                        |
| u_line_default_location_id | Many2one    | Computed field used for UI only. Used to determine the default location to set on a new inventory line (if the adjustment is against one location, this will be used) |
| u_line_readonly_location_id | Boolean    | Computed field used for UI only. Used to determine whether the location on a inventory line can be changed (if the adjustment is against one location that doesn't have any children, only this should be set, so can't be changed) |
| u_line_default_product_id | Many2one    | Computed field used for UI only. Used to determine the default product to set on a new inventory line (if the adjustment is against one product, this will be used) |
| u_line_readonly_product_id | Boolean    | Computed field used for UI only. Used to determine whether the product on a inventory line can be changed (if the adjustment is against one product, only this should be set, so shouldn't be changed) |

### Product (model: product.product)
Add support for searching only products within an inventory adjustment.

| Method  | Description |
|---------|-------------|
| _search | Extended to check for `search_restrict_inv_product_ids` in context, this is set when making changes to the `product_id` field on inventory lines. Will return only products that are set on the adjustment, if applicable. |
