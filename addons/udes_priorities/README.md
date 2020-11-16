# UDES Priorities

Module adds dynamic priorities (opposed to the hardcoded priorities and priority groups in udes_stock) to batches, pickings and moves. To achieve this another two models have been added `Priorities` and `Priority Groups`.
On batches, pickings and moves the priorities allowed to be assigned are filtered by the picking type.
If no picking type is assigned to a priority then it is allowed for all picking types.
Priorities have protected fields (`"reference", "sequence", "picking_type_ids", "group_ids", "active"`) which
can not be modified when there are outstanding pickings for the priority.
