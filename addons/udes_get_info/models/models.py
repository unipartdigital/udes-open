from odoo import fields, models, _
from odoo.addons.udes_common.models import add_if_not_exists
import logging

_logger = logging.getLogger(__name__)


# N.B: Basic values that some models have, no need to add them in _get_info_field_names
BASIC_GET_INFO_VALUES = {"id", "name", "display_name"}


@add_if_not_exists(models.BaseModel)
def _get_info(self, level=1, max_level=None, info_fields=None, extra_fields=None):
    """
    Returns the information of the current object. If level equals max_level it will return only
    BASIC_GET_INFO_VALUES of any relational field of the current object. If level is less than
    max_level it will return the specified fields of any relational fields of the current object.
    """
    self.ensure_one()

    if not max_level:
        max_level = self._get_info_max_levels
    next_level_and_max = {"level": level + 1, "max_level": max_level}
    if extra_fields is None:
        extra_fields = set()
    if info_fields is None:
        info_fields = self._get_info_field_names | BASIC_GET_INFO_VALUES | extra_fields

    info = {}
    for field_name in info_fields:
        # Allow for name to be changed in info output
        if isinstance(field_name, tuple):
            info_name, field_name = field_name
        else:
            info_name = field_name

        if field_name not in self:
            # skip over fields which don't exist and logging warning on server logs
            _logger.warning(_("Cannot find field name %s"), field_name)
            continue

        result = self[field_name]
        if isinstance(self[field_name], models.BaseModel):
            # Don't passing model fields if level has reached the max level.
            # This is done in order to get out of the recursive function.
            if not result:
                continue
            # If field is Many2one return dict, otherwise list of dicts.
            # Passing extra fields means that it will look for extra fields on every level.
            # Example if needed default_barcode from product and the field is not
            # in _get_info_field_names or in BASIC_GET_INFO_VALUES when calling get_info
            # from quants we can call it like: quants.get_info(extra_fields={"default_barcode"})
            # Note: default_barcode will be picked from every model that field exist and will
            # log warnings on every model not found
            if level == max_level:
                next_info_fields = {"info_fields": BASIC_GET_INFO_VALUES}
            else:
                next_info_fields = {"extra_fields": extra_fields}
            if isinstance(self._fields.get(field_name), fields.Many2one):
                _info = result._get_info(**next_info_fields, **next_level_and_max)
            else:
                _info = result.get_info(**next_info_fields, **next_level_and_max)
        else:
            _info = result

        info[info_name] = _info

    return info


@add_if_not_exists(models.BaseModel)
def get_info(self, **kwargs):
    return [x._get_info(**kwargs) for x in self]


if not hasattr(models.BaseModel, "_get_info_field_names"):
    setattr(models.BaseModel, "_get_info_field_names", set())


if not hasattr(models.BaseModel, "_get_info_max_levels"):
    setattr(models.BaseModel, "_get_info_max_levels", 1)
