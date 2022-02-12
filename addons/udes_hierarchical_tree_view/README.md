# UDES Hierarchical Tree View
Based on [owl_tutorial_views](https://github.com/Coding-Dodo/owl_tutorial_views.git)

Adds a new view type using OWL framework to show a hierarchical view of records on a model.
## Prerequisites
If you intend to add a hierarchical tree view onto a model, the model will require the following:
- either `child_id` or `child_ids` column. Handling for both is supported as Odoo has some One2many columns without the suffixed 's'. Links to same model as self.
- `parent_id` column. Handling only for this column name is supported. Links to same model as self.
- `_parent_name = "parent_id"` set
- `_parent_store = True` set
- `parent_path = fields.Char(index=True)` column on the model. Magically updated when `_parent_store` is set to True. Generates a path used by the hierarchy view.
- `view_ids` with a valid view_mode of `form` defined on the action. See Usage. This is needed for the form view ID to be scoped into the JS model.


## Options
The following options can be applied on the hierarchical tree node in the view like so:
```xml
<hierarchical_tree count_field="some_count_field" disable_drag_drop="1" show_form_button="1" />
```
Parsing falsey values from these columns (like `disable_drag_drop="0"`)is not supported (though `disable_drag_drop=""` would work!), so if you do not wish to use these options, simply remove them entirely

### count_field
Allows to assign an Integer field to show a count bubble on a TreeItem node.

### disable_drag_drop
Disables the drag/drop functionality for switching parent/child relationships.

By default, drag/drop is enabled

### show_form_button
Determines whether or not to display a button next to each TreeItem node to open that node in the default form view

By default, button will not be shown.

## Usage
Given all prerequesites are met - simply add `hierarchical_tree_view` to the view_mode on the `ir.actions.act_window`, and define an `ir.ui.view` template which contains a `hierarchical_tree` node:
```xml
<!-- Hierarchical Tree view -->
<record id="some_model_hierarchical_tree" model="ir.ui.view">
    <field name="name">some.model.hierarchical.tree</field>
    <field name="model">some.model</field>
    <field name="arch" type="xml">
        <hierarchical_tree count_field="some_count_field" disable_drag_drop="1" show_form_button="1" />
    </field>
</record>

<!-- Action window -->
<record id="some_model_action" model="ir.actions.act_window">
    <field name="name">Some Model Name</field>
    <field name="type">ir.actions.act_window</field>
    <field name="res_model">some.model</field>
    <field name="view_mode">tree,hierarchical_tree,form</field>
    <field name="view_ids" eval="[(5, 0, 0),
        (0, 0, {'view_mode': 'tree', 'view_id': ref('some_tree_view_extid')}),
        (0, 0, {'view_mode': 'form', 'view_id': ref('some_form_view_extid')})]" />
</record>
```

## Roadmap
### Add start_unfolded param to hierarchy node
This would automatically unfold all nodes in the hierarchy on view initialisation.

By default, nodes would start folded.

### Dynamically find default form view
Instead of needing to define view_ids on the action explicitly, we should dynamically find the default form fallback and use that if possible.

### Make the view responsive
Currently the view is static width and ideally should be made to be responsive
