# Suggested Locations

Module to handle suggested locations

# Dependencies
- base
- udes_get_info 
- udes_common (requires groupby)
- udes_stock (requires get_empty children)

# Policies (u_suggest_location_policy)

Policies are based on a metaclass that enforces the methods needed for suggested locations to work. Essentially they are used to govern how stock is moved within a warehouse, along with the u_drop_location_constaint.

| Policy | Description |
| - | - |
| ByEmpty | Suggest empty locations |
| ExactlyMatchMoveLine | Suggest the destination that matches the move line's destination location |
| ByProduct | Match drop locations to locations which are already store the product being dropped off |

# Drop Configurations (u_drop_location_constaint)

For flexibility there are a range of different configurations on which locations items can be dropped in a warehouse, ranging from ones where no checks are done giving the user freedom of choice, to ones that are more restrictive and only allow the item to be dropped in a particular set of locations. 

| Name | Description |
| - | - |
| do_not_scan | Don't require scanning the destination location |
| scan | The user has complete autonomy and scans the destination location which is chosen by the user |
| suggest | A user is given suitable locations (not empty) to drop the items based on the current policy, but ultimately can choose where they drop it |
| suggest_with_empty | A user is given suitable locations (including empty ones) to drop the items based on the current policy, but ultimately can choose where they drop it  |
| enforce | A user must drop the items in a suggested location (cannot be empty) based on the policy. User has no autonomy on where stock should be placed |
| enforce_with_empty | A user must drop the items in a suggested location (including empty locations) based on the policy. User has no autonomy on where stock should be placed |

# Models

## stock.picking.type

| Fields | Description | Extra Detail |
| - | - | - |
| u_suggest_locations_policy | The policy used to suggest locations | There is no policy by default |
| u_drop_location_constraint | Whether drop locations should be scanned, suggested and, then, enforced | Only the enforce and enforce_with_empty configuration currently validates the sugggested locations. The fields with 'empty' obviously include empty locations in the suggested locations - there is no prioritsation of these.  Default behaviour is 'scan' |

## stock.move.line

| Helper functions | Description | Extra Detail |
| - | - | - |
| _get_policy_class() | Get the policy for suggesting locations | - |
| suggest_locations() | Suggest locations for move line | The suggested locations can be obtained via self, or the picking_type and values. |
| validate_location_dest() | Check the drop location is valid | - | 

## stock.move

| Helper functions | Description | Extra Detail |
| - | - | - |
| _prepare_move_line_vals() | Extend default function to use our own suggested location strategy | It accepts a value error when calling suggest_locations in stock.move.line to avoid throwing an error if no policy is set. |
