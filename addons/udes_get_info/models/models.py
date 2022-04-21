"""
Provide get_info method and functionality.

This module automatically adds a get_info method to all models that inherit
from models.BaseModel.
"""
from odoo import fields, models, _
from odoo.addons.udes_common.models import add_if_not_exists
import logging

_logger = logging.getLogger(__name__)


# N.B: Basic values that some models have, no need to add them in _get_info_field_names
BASIC_GET_INFO_VALUES = {"id", "name", "display_name"}


@add_if_not_exists(models.BaseModel)
def get_info(self, level=1, info_fields=frozenset(), extra_fields=frozenset(), **kwargs):
    """
    Return the information of the current recordset as a list of dicts.

    The default information is BASIC_GET_INFO_VALUES plus the model's
    _get_info_field_names attribute.
    Arguments:
        level: int: the number of times to recurse through related objects.
               level=0 will return only scalar values on the object that called get_info initially.
               level=1 will return level=0 plus the results of calling get_info on related objects.
               level=2 will return level=1 plus the results of calling get_info on the related objects of related objects etc.
               etc.
        info_fields: set[str|tuple[str,str]]: return only these fields, overriding the defaults
        extra_fields: set[str[tuple[str, str]]: return these fields in addition to the defaults; ignored if info_fields is provided
    Fields may be defined as a tuple (alt_name, attr_name), in which case the
    alternative name will be used instead of the attribute name in the returned dicts.
    """
    return [
        x._get_info(level=level, info_fields=info_fields, extra_fields=extra_fields, **kwargs)
        for x in self
    ]


@add_if_not_exists(models.BaseModel)
def _get_info(self, level, info_fields, extra_fields):
    self.ensure_one()

    fields_to_fetch = (
        info_fields
        if info_fields
        else self._get_info_field_names | BASIC_GET_INFO_VALUES | extra_fields
    )

    info = {}
    for field_name in fields_to_fetch:
        # Allow for name to be changed in info output
        if isinstance(field_name, tuple):
            info_name, field_name = field_name
        else:
            info_name = field_name

        if field_name not in self:
            # Ignore fields which don't exist.
            _logger.debug(_("Cannot find field name %r on model %r"), field_name, self._name)
            continue

        result = self[field_name]
        if isinstance(self[field_name], models.BaseModel):
            # Stop recursing once we reach level zero or if the field is empty.
            if (level == 0) or (not result):
                continue
            # If field is Many2one return dict, otherwise list of dicts.
            # Passing extra fields means that it will look for extra fields on every level.
            # Example if needed default_barcode from product and the field is not
            # in _get_info_field_names or in BASIC_GET_INFO_VALUES when calling get_info
            # from quants we can call it like: quants.get_info(extra_fields={"default_barcode"})
            # Note: default_barcode will be picked from every model that field exist and will
            # log a messsage for every model where it is not found.
            if isinstance(self._fields.get(field_name), fields.Many2one):
                _info = result._get_info(
                    level=level - 1, info_fields=info_fields, extra_fields=extra_fields
                )
            else:
                _info = result.get_info(
                    level=level - 1, info_fields=info_fields, extra_fields=extra_fields
                )
        else:
            _info = result

        info[info_name] = _info

    return info


if not hasattr(models.BaseModel, "_get_info_field_names"):
    # This is shared globally: make it immutable to prevent accidental modification.
    setattr(models.BaseModel, "_get_info_field_names", frozenset())
