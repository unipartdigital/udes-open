"""Base model enhancements"""

import logging
import itertools
from operator import itemgetter
from .. import tools

from odoo import models, api, _
from odoo.exceptions import ValidationError, UserError
from lxml import etree
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
from datetime import datetime

_logger = logging.getLogger(__name__)

# TODO: This is duplicated in edi to allow edi to be stand alone.
# Consider revising this.


def add_if_not_exists(cls):
    """Patch class to add a new method"""

    def wrapper(func):
        # pylint: disable=missing-docstring
        if hasattr(cls, func.__name__):
            _logger.debug("%s.%s is already defined" % (cls.__name__, func.__name__))
        else:
            setattr(cls, func.__name__, func)
        return func

    return wrapper


@add_if_not_exists(models.BaseModel)
def sliced(self, size=models.PREFETCH_MAX):
    """Return the recordset ``self`` split into slices of a specified size"""
    return tools.sliced(self, size=size, concat=lambda s: self.browse(x.id for x in s))


@add_if_not_exists(models.BaseModel)
def batched(self, size=models.PREFETCH_MAX):
    """Return the recordset ``self`` split into batches of a specified size"""
    return tools.ranged(self.sliced(size=size))


def getter(key):
    func = None
    for x in key.split("."):
        if func is None:
            func = itemgetter(x)
        else:
            func = lambda y, _func=func: itemgetter(x)(_func(y))
    return func


@add_if_not_exists(models.BaseModel)
def groupby(self, key, sort=True):
    """Return the recordset ``self`` grouped by ``key``

    The recordset will automatically be sorted using ``key`` as the
    sorting key, unless ``sort`` is explicitly set to ``False``.

    ``key`` is permitted to produce a singleton recordset object, in
    which case the sort order will be well-defined but arbitrary.  If
    a non-arbitrary ordering is required, then use :meth:`~.sorted` to
    sort the recordset first, then pass to :meth:`~.groupby` with
    ``sort=False``.

    Any recordsets within a tuple in ``key`` will be replaced with a list of IDs from each
    recordset.
    """

    def tuple_contains_recordset(tup):
        """Returns True if the supplied tuple contains a recordset, otherwise False"""
        for item in tup:
            if isinstance(item, models.BaseModel):
                return True
        return False

    def get_ids_from_recordset_in_tuple(tup):
        """
        Replaces each Recordset found within the supplied tuple
        with a list of ids from that recordset
        """
        temp_key = []
        for item in tup:
            next_key = item
            if isinstance(next_key, models.BaseModel):
                next_key = next_key.ids
            elif isinstance(next_key, tuple) and tuple_contains_recordset(next_key):
                next_key = get_ids_from_recordset_in_tuple(next_key)
            temp_key.append(next_key)
        return tuple(temp_key)

    recs = self
    if isinstance(key, str):
        key = itemgetter(key)
    if sort:
        if recs:
            first_key = key(next(iter(recs)))
            if isinstance(first_key, models.BaseModel):
                recs = recs.sorted(key=lambda x: key(x).ids)
            elif isinstance(first_key, tuple) and tuple_contains_recordset(first_key):
                recs = recs.sorted(key=lambda x: get_ids_from_recordset_in_tuple(key(x)))
            else:
                recs = recs.sorted(key=key)
    return ((k, self.browse(x.id for x in v)) for k, v in itertools.groupby(recs, key=key))


@add_if_not_exists(models.BaseModel)
def statistics(self, cache=False):
    """Gather profiling statistics for an operation"""
    return tools.Statistics(self.env, cache=cache)


@add_if_not_exists(models.BaseModel)
def trace(self, filter=None, max=None):
    """Trace database queries"""
    return tools.QueryTracer(self.env.cr, filter=filter, max=max)


@add_if_not_exists(models.BaseModel)
def selection_display_name(self, selection_field_name):
    """Get the display name - for a given selection fields value - on a recordset
    :param: self: <some.model> recordset (len 1) to get the value from
    :param: selection_field_name: str() field name to get the value for

    :returns: str() Display name of the currently set selection field value of the recordset
    """
    self.ensure_one()
    try:
        selection_field = self._fields[selection_field_name]
    except KeyError:
        raise ValidationError(
            _(f"Field '{selection_field_name}' does not exist on model '{self._name}'")
        )
    # Odoo has a nice function that handles all the weird ways you can define selections!
    selection_values_dict = dict(selection_field._description_selection(self.env))
    return selection_values_dict.get(self[selection_field_name], False)


class Base(models.AbstractModel):
    _inherit = "base"

    # Adding a default empty list for base model, it will be override when needed for
    # specific models.
    DetailedFormViewFields = []

    @api.model
    def fields_view_get(self, view_id=None, view_type="form", toolbar=False, submenu=False):
        """Override fields_view_get to remove/hide information that is specified in models"""
        res = super().fields_view_get(view_id, view_type, toolbar, submenu)
        doc = etree.XML(res["arch"])
        if self._context.get("view_all_fields"):
            # Hide the view more button
            doc = etree.XML(res["arch"])
            for node in doc.xpath("//button[@name='action_detailed_view']"):
                node.getparent().remove(node)
        else:
            if not self.DetailedFormViewFields:
                return res
            if view_type == "form":
                for field_name in self.DetailedFormViewFields:
                    for node in doc.xpath("//field[@name='%s']" % field_name):
                        node.getparent().remove(node)
        res["arch"] = etree.tostring(doc)
        return res

    def base_model_detailed_view(self, model, form_view):
        """Main method which can be called from all models to redirect to a form view with context
        view_all_fields True in order to remove the fields that are configured in helpers"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_model": "form",
            "views": [(form_view.id, "form")],
            "res_model": model,
            "view_id": form_view.id,
            "res_id": self.id,
            "context": {"view_all_fields": True},
        }

    @api.model
    def _create(self, vals):
        """Inheriting low level _create method to check if there is any date or datetime field less
        than a static year 1000. In that case raise an error to show the users that the date entered
         is not correct

         On Core _create method vals are expected to be a list
        """
        for val in vals:
            if isinstance(val.get("stored"), dict):
                self.validate_values_of_date_fields(val.get("stored"))
        res = super()._create(vals)
        return res

    def _write(self, vals):
        """Inheriting low level _write method to check if there is any date or datetime field less
        than a static year 1000. In that case raise an error to show the users that the date entered
         is not correct"""
        if isinstance(vals, dict):
            self.validate_values_of_date_fields(vals)
        res = super()._write(vals)
        return res

    @api.model
    def validate_values_of_date_fields(self, values):
        """
        Checking if date or datetime fields that are formatted as string
        can be converted to a date field and the year is greater than 1000.
        Raising error in case year is less than 1000
        """
        date_fields = {
            key: value
            for key, value in self._fields.items()
            if value.type in ("date", "datetime") and key not in ("write_date", "create_date")
        }
        date_values = {
            k: v for k, v in values.items() if k in date_fields and isinstance(v, str) and v
        }
        for date_value in date_values.values():
            try:
                date_field = datetime.strptime(date_value[:10], DATE_FORMAT)
            except:
                raise UserError(_("Date '%s' is not valid.") % date_value)
            if date_field.year < 1000:
                raise UserError(_("Date '%s' is not valid.") % date_value)

    def record_is_child_of_self(self, child_record):
        """
        Returns true if `child_record` is a child of the record in self, including if it is
        the same record as in self. Otherwise False.

        Raises TypeError if the user tries to check a record is a child against a record
        from a different model.

        Raises ValueError if the model doesn't have a parent/child hierarchy setup
        (i.e. doesn't have the `parent_path` field).
        """
        self.ensure_one()
        child_record.ensure_one()

        common_error_msg = "Unable to check if %s is child of %s."
        if self._name != child_record._name:
            raise TypeError(
                _(f"{common_error_msg} Records are from different models.")
                % (child_record, self)
            )
        if "parent_path" not in self._fields:
            raise ValueError(
                _(f"{common_error_msg} Model '%s' doesn't have a parent/child hierarchy.")
                % (child_record, self, self._name)
            )

        return self.parent_path in child_record.parent_path
