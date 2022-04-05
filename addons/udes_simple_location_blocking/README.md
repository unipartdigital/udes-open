# UDES Simple Location Blocking
This module implements the logic to allow the blocking of a location. This includes checking and blocking operations that
try to use a blocked location. Also avoid returning locations that are blocked when performing a stock inventory check,
a picking, setting a location for a stock move or move line or when retrieving product quantities for a location. 

## Default settings
None

## Requires
- stock:
  This module needs to inherit and add functionality to models from stock 

## Models

### Inventory (model: stock.inventory)
Constrain location_ids field to ensure no blocked locations are used in a stock inventory.

| Function     | Description                                                                                              |
|--------------|----------------------------------------------------------------------------------------------------------|
| _action_done | Checks that none of the locations used are blocked and then tries to set an inventory adjustment to done |

### Inventory Line (model: stock.inventory)
Constrain location_id field to ensure no blocked locations are used in a stock inventory line.

### Locations (model: stock.location)
This model is expanded to include a simple way to block a location with the use of a flag/boolean field.

| Field Name       | Type    | Description                                                           |
|------------------|---------|-----------------------------------------------------------------------|
| u_blocked        | Boolean | True if the location is black, False otherwise                        |
| u_blocked_reason | Char    | One or multiple reasons for the location being blocked, not required  |

| Helpers                                   | Description                                                                                                         |
|-------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| check_blocked                             | Checks whether a location or more are blocked and raises a ValidationError .                                        |
| _prepare_blocked_msg                      | Returns a string with the reason why one or more locations are blocked                                              |
| onchange_u_blocked                        | Set the u_blocked_reason to an empty string when the location is unblocked on a form                                |
| _check_reserved_quants_and_blocked_reason | Checks that when a location is blocked there are no stock quantities reserved and that a reason for blocking is set |

### Stock Moves (model: stock.move)
Constrain location_id and location_dest_id fields to ensure no blocked locations are used in a stock move.

### Stock Move Lines (model: stock.move.line)
Constrain location_id and location_dest_id fields to ensure no blocked locations are used in a stock move line.

### Pickings (model: stock.picking)
Constrain location_id and location_dest_id fields to ensure no blocked locations are used in a picking.

### Quants (model: stock.quant)
Add functionality to ensure quantities of products in blocked locations are not retrieved/used.

| Function  | Description                                                              |
|-----------|--------------------------------------------------------------------------|
| _gather   | Returns the quantities of a product in a location when it is not blocked |

## Future work:
