"""Dodgy field"""

from odoo import fields
from odoo.tools import pycompat


class Integer(fields.Integer):
    """
    Modified Integer Field.

    This field reads its value from the database when it is computed as the
    value in the cache may not be correct.
    """

    def _compute_value(self, records):
        """Invoke the compute method on ``records``."""
        # initialize the fields to their corresponding null value in cache
        fields = records._field_computed[self]
        cache = records.env.cache
        for field in fields:
            for record in records:
                value = record.read([field.name], load="_classic_write")
                value = value[0][field.name] if value else False
                cache.set(record, field, field.convert_to_cache(value, record, validate=False))
        if isinstance(self.compute, pycompat.string_types):
            getattr(records, self.compute)()
        else:
            self.compute(records)
