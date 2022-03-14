# UDES Stock Refactoring
UDES Stock Refactoring module refactors picks by merging pickings or splitting them depending on the grouping key.
The module contains different ways how handles the refactoring:
1. It is done automatically depending on configuration that is set on the picking type.
2. Default Refactoring by triggering the configuration on picking type with a wizard by selecting one or multi records(moves, picks or batches) with the needed picking type to be refactored.
3. Custom Refactoring by selecting one or multi records(moves, picks or batches) with the needed picking type to be refactored and specifying the group key in the wizard.
  The selected grouping factor should have a configuration set up on the picking type even if is not automatically triggered on flow change.
## Default settings

- data/picking_types.xml
    - Goods OUT (stock.picking_type_out)
    - Putaway (udes_stock.picking_type_putaway)
    
## Requires
- udes_common:
  Because imports RegistryMeta from models/registry used when defining refactor abstract classes
- stock_picking_batch:
  The reason is as in module functionalities are included refactoring of stock picking batches , 
  and the model is defined in stock_picking_batch module. 
- base:
  Access rights are not defined yet but still in order to see new models, agreed to assign to System User group.
  Group is defined in base module.
- udes_stock: 
  Is inheriting putaway picking type which is defined in udes_stock module. 

There are other modules which are required and they got added automatically by dependence hierarchy

## Models
In general the functions are designed to be as simple as possible, where they do one thing well.

### Stock Picking Type(model: stock.picking.type)

Stock Picking Type is inherited to add more configurations fields in order to handle the refactoring

| Field Name | Type | Description |
| ---------- | ---- | ----------- |
| u_move_line_key_format     | Char | A field name on stock.move.line that can be used to group move lines|
| u_move_key_format | Char | A field name on stock.move that can be to group move |
| u_post_confirm_action | Selection | Extendable options to choose the action to be taken after confirming a picking|
| u_post_assign_action | Selection | Extendable options to choose the action to be taken after reserving a picking|
| u_post_validate_action | Selection | Extendable options to choose the action to be taken after validating a picking|

### Stock Picking Batch (model: stock.picking.batch)

Model is inherited to compute picking types in a batch, which is helpful in _refactor_action_batch_pickings_by method

| Field Name | Type | Description |
| ---------- | ---- | ----------- |
| picking_type_ids | One2Many [{stock.picking.type}] | Operation Types|

### Stock Picking (model: stock.picking)

Model is inherited to add refactoring methods and to include the methods when confirming, reserving or validating with super calls

| Field Name | Type | Description |
| ---------- | ---- | ----------- |

| Helpers | Description |
| ------- | ----------- | 
| _get_default_new_picking_for_group_values | Return base values which can be extended for the new picking|
| _remove_misleading_values | Updating values of the new picking to avoid misleading values|
| _new_picking_for_group |  Find existing picking for the supplied group, if none found create a new one.|
| _prepare_extra_info_for_new_picking_for_group |  Prepare the extra info for the new pickings that might be created for the group of moves.|
| action_confirm | Inheriting with super in order to delete empty pickings after refactoring on confirm|
| action_assign | Inheriting with super in order to delete empty pickings after refactoring on reserve|
| _action_done | Inheriting with super in order to delete empty pickings after refactoring on validate|

### Stock Move Line (model: stock.move.line)

| Field Name | Type | Description |
| ---------- | ---- | ----------- |
| u_grouping_key | Char | Grouping key|

| Helpers | Description |
| ------- | ----------- | 
| group_by_key | Check each picking type has a move line key format set and return the groupby|

### Stock Move (model: stock.move)

| Field Name | Type | Description |
| ---------- | ---- | ----------- |
| u_grouping_key | Char | Grouping key|

| Helpers | Description |
| ------- | ----------- | 
| group_by_key | Check each picking type has a move key format set and return the groupby.|
| action_refactor | Refactor all the moves in self. May result in the moves being changed and/or their associated pickings being deleted.|
| _action_confirm | Extend _action_assign to trigger refactor action on move confirmation.|
| _action_assign | Extend _action_assign to trigger refactor action on move reservation.|
| _action_done | Extend _action_assign to trigger refactor action on move validation.|
| refactor_by_move_groups | Refactoring moves if in picking type is GroupByMoveKey set.|
| refactor_by_move_line_groups | Refactoring moves if in picking type is GroupByMoveLineKey set.|
| _refactor_action_batch_pickings_by | Move the pickings of the moves in this StockMove into draft batches grouped by a given key.|

### GroupByMoveLineKey Abstract Class

Group the move lines by the splitting criteria. Extending trigger action selections fields on stock picking type

| Helpers | Description |
| ------- | ----------- | 
| do_refactor | Refactoring moves by stock move line grouping key if it is set on picking type.|

Extends u_post_assign_action and u_post_validate_action with options of enabling refactoring after reservation or validation of pickings.

### GroupByMoveKey Abstract Class

Group the moves by the splitting criteria. Extending trigger action selections fields on stock picking type

| Helpers | Description |
| ------- | ----------- | 
| do_refactor | Refactoring moves by stock move grouping key if it is set on picking type.|

Extends u_post_confirm_action, u_post_assign_action and u_post_validate_action with options of enabling refactoring after confirmation, reservation or validation of pickings.

### BatchPickingsByDatePriority Abstract Class

Refactor pickings by scheduled date and priority.

| Helpers | Description |
| ------- | ----------- | 
| do_refactor | Batch pickings by date and priority.|

Extends u_post_confirm_action with options of enabling refactoring after confirmation pickings.

### BatchPickingsByDate Abstract Class

Refactor pickings by scheduled date.

| Helpers | Description |
| ------- | ----------- | 
| do_refactor | Batch pickings by date.|

Extends u_post_confirm_action with options of enabling refactoring after confirmation pickings.

### Refactor Abstract Class

Main abstract class where all the other abstract classes will be inherited. Purpose of defining the class is
to create commune attributes like name, description and get_selection in order to show as an option in selection fields of refactoring actions. 


### Refactor Criteria (models.TransientModel: refactor.criteria)

| Field Name | Type | Description |
| ---------- | ---- | ----------- |
| refactor_action | Selection | Custom refactor action to be applied in case of custom refactor|
| custom_criteria | Bool | By default is False, if change to True than we may apply custom refactoring|

### Refactor Stock Picking Batch (models.TransientModel: stock.picking.batch.refactor.wizard)

Class inherits from TransientModel class refactor.criteria the only difference is the source model from where this wizard is opened.


| Helpers | Description |
| ------- | ----------- | 
| do_refactor | Refactoring stock moves in selected batches.|

### Refactor Stock Picking (models.TransientModel: stock.picking.refactor.wizard)

Class inherits from TransientModel class refactor.criteria the only difference is the source model from where this wizard is opened.

| Helpers | Description |
| ------- | ----------- | 
| do_refactor | Refactoring stock moves in selected pickings.|

### Refactor Stock Move (models.TransientModel: stock.move.refactor.wizard)

Class inherits from TransientModel class refactor.criteria the only difference is the source model from where this wizard is opened.

| Helpers | Description |
| ------- | ----------- | 
| do_refactor | Refactoring stock moves in selected moves.|
