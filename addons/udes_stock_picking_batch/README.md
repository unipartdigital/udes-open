# UDES Stock Picking Batch 
The batch functionality related to pickings and picking types lives here.  

## Default Settings 

## Requirements 
- base:
  Is specifically used to inherit views and for access right groups.
- stock:
  Is specifically used to inherit views.
- udes_security:
  Is specifically used for access right groups.
- stock_picking_batch:
  Stock picking batch odoo core module where functionalities are developed.
- udes_get_info:
  Using get_info method on mixin model which is a generic method.


## Models 

### stock.picking.batch
The main class for handling batch transfers in warehouse management

| Field Name                  | Type                       | Description                                                                                          |
|-----------------------------|----------------------------|------------------------------------------------------------------------------------------------------|
| u_last_reserved_pallet_name |    string                  | Barcode of the last pallet used in the batch.                                                        |
| u_ephemeral                 |    boolean                 | Ephemeral batches are unassigned if the user logs out                                                |
| priority                    | selection(string)          | Priority of a batch is the maximum priority of its pickings.                                         |
| user_id                     | Many2one {{res.users}}     | User assigned to a batch. Changed to allow editing of the field in different states of the batch     |
| state                       | Selection                  | State of the batch: draft, waiting, ready, in_progress, done, cancel                                 |
| picking_ids                 | One2many {{stock.picking}} | Pickings assigned to a batch. Changed to allow editing of the field in different states of the batch |
| u_original_name             |    Char                    | Name of the batch from which this batch was derived                                                  |
| picking_type_ids            | Many2Many                  | Picking types in the batch                                                                           |


| Helpers                                  | Description                                                                                               |
|------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| is_valid_location_dest_id                | Whether the specified location is a valid putaway location for the relevant pickings of the batch         |
| add_extra_pickings                       | Get the next possible available pickings and add them to the batch that current user is operating         |
| get_batch_priority_group                 | Get priority group for this batch based on the pickings' priorities                                       |
| check_same_picking_priority              | Checks if pickings priorities matches with batch priority                                                 |
| get_log_batch_picking_flag               | Get u_log_batch_picking configuration from warehouse and user name                                        |
| reserve_pallet                           | Reserves a pallet for use in a batch                                                                      |
| _get_task_grouping_criteria              | Return a function for sorting by picking, package(maybe), product, and location                           |
| get_available_move_lines                 | Get all the move lines from a batch available pickings                                                    |
| get_next_tasks                           | Get the next not completed tasks of the batch to be done                                                  |
| get_next_task                            | Get first task of next not completed tasks of the batch to be done                                        |
| get_completed_tasks                      | Get all completed tasks of the batch                                                                      |
| _populate_next_tasks                     | Populate the next tasks according to the given criteria                                                   |
| _populate_next_task                      | Populate the next task from the available move lines and grouping                                         |
| _get_move_lines_to_drop_off              | Getting all move lines of the batch that are ready to drop off                                            |
| get_next_drop_off                        | Based on the criteria specified for the batch picking type, determines what move lines should be dropped  |
| drop_off_picked                          | Validate the move lines of the batch by moving them to the specified location                             |
| _compute_state                           | Recompute batch state if no lock_batch_state variable in the context                                      |
| _mark_as_todo                            | Moves batch from draft to waiting, then recompute state of the batch                                      |
| _action_confirm                          | Moves batch to waiting, then tries to assign the pickings in the batch and recompute state                |
| _assign_picks                            | Tries to assign all pickings in a batch if u_auto_assign_batch_pick is True and then recompute state      |
| _remove_unready_picks                    | Tries to remove unready pickings if the u_remove_unready_batch batch is True                              |
| done_picks                               | Returns pickings in state done or cancel                                                                  |
| ready_picks                              | Returns pickings in state assigned                                                                        |
| unready_picks                            | Returns pickings in state draft, waiting or confirmed                                                     |
| get_single_batch                         | Search for a picking batch in progress for the specified user                                             |
| _check_user_id                           | Check the user id is valid - user_id = False will raise an exception.                                     |
| get_user_batches                         | Search for all batches attached to a given user_id                                                        |
| assign_batch                             | Return all batches that are ready, have the relevant picking type, and the passed selection criteria      |
| _select_batch_to_assign                  | Orders the batch by name and returns the first one                                                        |
| create_batch                             | Create and return a batch for the specified user if pickings exist.                                       |
| _check_user_batch_has_same_picking_types | Check if a user has a batch with different picking types                                                  |
| _check_user_batch_in_progress            | Check if a user has a batch in progress                                                                   |
| _create_batch                            | Create a batch for a user by including pickings with the specified picking_type_id and picking priorities |
| close                                    | Un-assign incomplete pickings from batches                                                                |
| _copy_continuation_batch                 | Copy a batch and add the provided pickings                                                                |
| remove_unfinished_work                   | Remove pickings from batch if they are not started                                                        |
| _compute_picking_type                    | Computes the picking_type_ids in the batch                                                                |
| unpickable_item                          | Implements unpickable items functionality by creation of backorders and stock investigation pickings      |

| Global Methods | Description                     |
|----------------|---------------------------------|
| get_next_name  | Get the next name for an object |

### stock.picking.type
The type of stock.picking can be defined by this type. It can represent a goods in, a putaway, an internal transfer, a pick, a goods out, or any other collection of stock moves the warehouse operators want to model within UDES.

| Field Name                    | Type               | Description                                                                                                                 | 
|-------------------------------|--------------------|-----------------------------------------------------------------------------------------------------------------------------|
| u_use_location_categories     | boolean            | Flag to indicate whether to ask the user to select location categories when starting the pick process. Location categories  |
| u_batch_dest_loc_not_allowed  | boolean            | When batch chooses picking it filter out pickings which has block destination location                                      |
| u_reserve_pallet_per_picking  | boolean            | If enabled, each picking in a batch will be associated with an individual pallet                                            |
| u_max_reservable_pallets      | integer            | Maximum pallets that may be simultaneously reserved in a batch                                                              |
| u_allow_swapping_packages     | boolean            | Flag to indicate if is allowed to swap suggested package with a same content package in same location during operations     |
| u_return_to_skipped           | boolean            | Flag to indicate if the skipped items will be returned to in the same batch                                                 |
| u_drop_criterion              | selection(string)  | Way of grouping items when are ready to drop off, from a defined list of options( by products, by packages, by orders       |
| u_auto_assign_batch_pick      | Boolean            | Flag to enable to reserve stock when pickings are added to a running batch                                                  |
| u_remove_unready_batch        | Boolean            | Flat to enable to remove pickings that cannot be reserved when added to a running batch                                     |
| u_auto_batch_pallet           | boolean            | Flag to indicate whether picking type will automatically create batches when the user scans the pallet                      |
| u_create_batch_for_user       | boolean            | Flag to indicate whether to create a new batch and assign it to the user, if he does not have one already assigned          |
| u_assign_batch_to_user        | boolean            | Flag to indicate whether to assign a "ready" batch to the user, if he does not have one already assigned                    |

### stock.picking
This is essentially a collection of products that are to be moved from one location to another.

| Field Name              | Type      | Description                                                                                         | 
|-------------------------|-----------|-----------------------------------------------------------------------------------------------------|
| u_location_category_id  | Many2one  | Used to know which pickers have the right equipment to pick it                                      |
| u_reserved_pallet       | string    | If reserving pallets per picking is enabled, this field stores the pallet reserved for this picking |

| Helpers                           | Description                                                                                           |
|-----------------------------------|-------------------------------------------------------------------------------------------------------|
| get_move_lines_done               | Return the recordset of move lines done                                                               |
| is_valid_location_dest_id         | Whether the specified location or location reference is a valid putaway location for the picking      |
| search_for_pickings               | Search for next available pickings based on picking type and priorities                               |
| get_priorities                    | Return a list of dicts containing the priorities of the all defined priority groups                   |
| _priorities_has_ready_pickings    | Check if priorities have already ready pickings                                                       |
| _trigger_batch_confirm_and_remove | Recompute batch state after assigning and removing picks based on flags                               |
| _trigger_batch_state_recompute    | Recompute batch state after removing picks based on flags                                             |
| _action_assign                    | Always recompute batch state after assigning picking because @api.constraint is not working correctly |
| write                             | Ensure we recompute batches that were removed from a picking                                          |
| batch_to_user                     | Validates that a user can be assigned to a batch, then creates the batch for a picking.               | 

### stock.move.line

| Helpers                               | Description                                                                                                                          |
|---------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| _determine_priority_skipped_moveline  | Returns a priority move line based on the first move line found that matches either the skipped product ids or skipped move_line_ids |
| _prepare_task_info                    | Prepare info of a task in a dict format                                                                                              |
| _drop_off_criterion_summary           | Generate product summary for drop off criterion for the move lines.                                                                  |

### stock.warehouse 
Provides warehouse configuration.

| Field Name                  | Type             | Description                                                | 
|-----------------------------|------------------|------------------------------------------------------------|
| u_log_batch_picking         |    boolean       | Logs details when picking is added to batch picking        |

### res.users
Handles all users of UDES. Have informations about login credentials, access rights etc.

| Field Name                  | Type             | Description                                                | 
|-----------------------------|------------------|------------------------------------------------------------|
| u_location_category_ids     |    Many2many     | Location categories of the user                            |
