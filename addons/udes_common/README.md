# UDES Common
Common suite of helper functions used across all of UDES

## Helper functions
### BaseModel
#### add_if_not_exists()
To be used as a decorator, as an easy way to patch functions into models.
##### Usage
```python
from odoo.addons.udes_common.models import add_if_not_exists
from odoo import models

@add_if_not_exists(models.BaseModel)
def some_function(self):
    print("some_function() is callable from all odoo models now!")
```

#### sliced()
Return the recordset `self` split into slices of a specified size
##### Usage
```python
print(my_recordsets)
> stock.move.line(1,2,3,4,5)
for sliced_recs in my_recordsets.sliced(size=2):
    print(sliced_recs)
> stock.move.line(1,2)
> stock.move.line(3,4)
> stock.move.line(5,)
```

#### batched()
Return the recordset `self` split into batches of a specified size
##### Usage
```python
print(my_recordsets)
> stock.move.line(1,2,3,4,5)
for r, batch in my_recordsets.batched(size=2):
    print(f"Processing move lines {r[0] + 1}-{r[-1] + 1} of {len(my_recordsets)}")
    print(batch)
> Processing move lines 1-2 of 5
> stock.move.line(1,2)
> Processing move lines 3-4 of 5
> stock.move.line(3,4)
> Processing move lines 5-5 of 5
> stock.move.line(5,)
```

#### groupby()
Return the recordset `self` grouped by `key`

The recordset will automatically be sorted using `key` as the sorting key, unless `sort` is explicitly set to `False`.

`key` is permitted to produce a singleton recordset object, in which case the sort order will be well-defined but arbitrary. If a non-arbitrary ordering is required, then use :meth:`~.sorted` to sort the recordset first, then pass to :meth:`~.groupby` with `sort=False`.
##### Usage
```python
print(my_recordsets)
> stock.move.line(1,2,3,4)
for product, move_lines in my_recordsets.groupby("product_id"):
    print(product.name)
    print(move_lines)
> "Angry Aubergine"
> stock.move.line(1,2)
> "Benevolent Banana"
> stock.move.line(3,4)
```

#### statistics()
Gather profiling statistics for an operation
##### Usage
```python
with self.statistics() as stats:
    # do something
_logger.info(f"Took {stats.elapsed} seconds, did {stats.count} queries")
```

#### trace()
Trace database queries

#### selection_display_name()
Get the display name - for a given selection fields value - on a recordset
##### Usage
```python
print(some_recordset.report_type)
> "qweb-pdf"
print(some_recordset.selection_display_name("report_type"))
> "PDF"
```

### ir.module.module
#### is_module_installed()
Returns true if the supplied module exists
and is installed, otherwise false.
##### Usage
```python
IrModuleModule = self.env["ir.module.module"]
IrModuleModule.is_module_installed("my_module")
> False
```

### Registry
#### RegistryMeta
Used to manage abstract classes. Classes that will fall into the registry should be in a registry 
folder of respective module.
For example in `udes_suggest_location` ensuring that each location policy class created implements
all required methods and that each policy name is unique
