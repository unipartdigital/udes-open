# Suggested Locations

Module to handle suggested locations

# Dependencies
- base
- udes_common (require groupby)
- udes_stock (require get_empty children)

# Policies

Policies are based on a metaclass that enforces the methods needed for suggested locations to work. 

# stock.picking 

| Fields | Description | Extra Detail |
| - | - | - |
| u_suggest_locations_policy | The policy used to suggest locations | This is blank until added in the policies |
| u_drop_location_constraint | Whether drop locations should be scanned, suggested and, then, enforced | Only the enforce and enforce_with_empty configuration currently validates the sugggested locations. The fields with 'empty' obviously include empty locations in the suggested locations - there is no prioritsation of these.  |

# stock.move.line

| Fields | Description | Extra Detail |
| - | - | - |
| u_picking_type_id | Picking tpye id | - | 

| Helper functions | Description | Extra Detail |
| - | - | - |
| _get_policy_class() | Get the policy for suggesting locations | - |
| suggest_locations() | Suggest locations for move line | The suggested locations can be obtained via self, or the picking_type and values. |
| validate_location_dest() | Check the drop location is valid | - | 

# stock.move

| Helper functions | Description | Extra Detail |
| - | - | - |
| _prepare_move_line_vals() | Extend default function to use our own suggested location strategy | It accepts a value error when calling suggest_locations in stock.move.line to avoid throwing an error if no policy is set. |