# UDES Get Info
Add `get_info` helper method to the BaseModel in Odoo.

Allows for a convenient way to get a dictionary of fieldnames and values for a given recordset on any model (defaults are `["id", "name", "display_name"]`) along with a mechanism to update which field names should be retrieved from this function on a per-model basis

## Adding values to _get_info_field_names
If you want to extend `_get_info_field_names` on a model, use the following snippet (adding `company_id` on the model `stock.location` as an example)
```python
class Location(models.Model):

    _inherit = "stock.location"

    def _setup_complete(self):
        """Use setup complete call to add field"""
        super()._setup_complete()
        self.__class__._get_info_field_names.add("company_id")
```
