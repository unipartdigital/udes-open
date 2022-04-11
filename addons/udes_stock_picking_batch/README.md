# UDES Stock Picking Batch 
The batch functionality related to pickings and picking types lives here.

## Default Settings 

## Requirements 

## Models 

### stock.picking 
Most of the code in this model are constraints that implement the behaviour of the flags set in stock.picking.type model.
Also, we manually compute the state of the batch assigned to a picking to ensure we can assign/reserve pickings before we
compute the state of the batch.

| Helpers                           | Description                                                                                           |
|-----------------------------------|-------------------------------------------------------------------------------------------------------|
| _trigger_batch_confirm_and_remove | Recompute batch state after assigning and removing picks based on flags                               |
| _trigger_batch_state_recompute    | Recompute batch state after removing picks based on flags                                             |
| _action_assign                    | Always recompute batch state after assigning picking because @api.constraint is not working correctly |
| write                             | Ensure we recompute batches that were removed from a picking                                          |

### stock.picking.batch 
In this model we are changing the way in which a batch state is recomputed.

| Field Name   | Type                       | Description                                                                                          |
|--------------|----------------------------|------------------------------------------------------------------------------------------------------|
| user_id      | Many2one {{res.users}}     | User assigned to a batch. Changed to allow editing of the field in different states of the batch     |
| state        | Selection                  | State of the batch: draft, waiting, ready, in_progress, done, cancel                                 |
| picking_ids  | One2many {{stock.picking}} | Pickings assigned to a batch. Changed to allow editing of the field in different states of the batch |


| Helpers                 | Description                                                                                          |
|-------------------------|------------------------------------------------------------------------------------------------------|
| __compute_state         | Recompute batch state if no lock_batch_state variable in the context                                 |
| __mark_as_todo          | Moves batch from draft to waiting, then recompute state of the batch                                 |
| __action_confirm        | Moves batch to waiting, then tries to assign the pickings in the batch and recompute state           |
| __assign_picks          | Tries to assign all pickings in a batch if u_auto_assign_batch_pick is True and then recompute state |
| __remove_unready_picks  | Tries to remove unready pickings if the u_remove_unready_batch batch is True                         |
| done_picks              | Returns pickings in state done or cancel                                                             |
| ready_picks             | Returns pickings in state assigned                                                                   |
| unready_picks           | Returns pickings in state draft, waiting or confirmed                                                |

### stock.picking.type

| Field Name               | Type     | Description                                                                             |
|--------------------------|----------|-----------------------------------------------------------------------------------------|
| u_auto_assign_batch_pick | Boolean  | Flag to enable to reserve stock when pickings are added to a running batch              |
| u_remove_unready_batch   | Boolean  | Flat to enable to remove pickings that cannot be reserved when added to a running batch |
