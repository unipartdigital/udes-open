# -*- coding: utf-8 -*-
from odoo import models, _
from addons.udes_common.models import add_if_not_exists
import logging

_logger = logging.getLogger(__name__)


# N.B: Basic values should not have any relations as this is to stop the recursion
BASIC_GET_INFO_VALUES = {"id", "name", "display_name"}


@add_if_not_exists(models.BaseModel)
def _get_info(self, level=0, max_level=None, fields=None):

    self.ensure_one()

    if not max_level:
        max_level = self._get_info_max_levels
    if not fields:
        fields = self._get_info_field_names
    level_and_max = {"level": level + 1, "max_level": max_level}

    info = {}
    for field_name in fields:
        # Allow for name to be changed in info output
        if isinstance(field_name, tuple):
            info_name, field_name = field_name
        else:
            info_name = field_name

        if field_name not in self:
            # skip over fields which don't exist
            _logger.warning(_("Cannot find field name %s"), field_name)
            continue

        if isinstance(self[field_name], models.BaseModel):
            if level + 1 < max_level:
                _info = self[field_name]._get_info(fields=fields, **level_and_max)
            else:
                _info = self[field_name]._get_info(fields=BASIC_GET_INFO_VALUES, **level_and_max)
        else:
            _info = self[field_name]

        info[info_name] = _info

    return info


@add_if_not_exists(models.BaseModel)
def get_info(self, **kwargs):
    return [x._get_info(**kwargs) for x in self]


if not hasattr(models.BaseModel, "_get_info_field_names"):
    setattr(models.BaseModel, "_get_info_field_names", BASIC_GET_INFO_VALUES)


if not hasattr(models.BaseModel, "_get_info_max_levels"):
    setattr(models.BaseModel, "_get_info_max_levels", 1)
