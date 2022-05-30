from enum import IntEnum


class RelationalFieldOperators(IntEnum):
    """
    Operators used to set values on one2many and many2many fields.

    - Create (0, 0, values): Creates a new record created from the provided values dict.
    - Update (1, id, values): Updates an existing record of id with values provided in values dict.
    - Delete (2, id, 0): Deletes the record of id, thus removing it from the relational field.
    - Remove (3, id, 0): Removes the record of id from the relational field, but does not delete it.
    - Add (4, id, 0): Adds the record of id to the relational field.
    - RemoveAll (5, 0, 0): Removes all records from relational field, but does not delete them.
    - Replace (6, 0, ids): Replaces all records in the relational field with the ids provided.
    """
    Create = 0
    Update = 1
    Delete = 2
    Remove = 3
    Add = 4
    RemoveAll = 5
    Replace = 6
