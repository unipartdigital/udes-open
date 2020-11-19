# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo import api, models, tools


class MailTracking(models.Model):
    _inherit = "mail.tracking.value"

    @api.model
    def create_tracking_values(self, initial_value, new_value, col_name, col_info):
        """Stop tracking values"""
        tracked = True
        values = {
            "field": col_name,
            "field_desc": col_info["string"],
            "field_type": col_info["type"],
        }

        if col_info["type"] in ["integer", "float", "char", "text", "datetime", "monetary"]:
            values.update(
                {
                    "old_value_%s" % col_info["type"]: initial_value,
                    "new_value_%s" % col_info["type"]: new_value,
                }
            )
        elif col_info["type"] == "date":
            values.update(
                {
                    "old_value_datetime": (
                        initial_value
                        and datetime.strftime(
                            datetime.combine(
                                datetime.strptime(initial_value, tools.DEFAULT_SERVER_DATE_FORMAT),
                                datetime.min.time(),
                            ),
                            tools.DEFAULT_SERVER_DATETIME_FORMAT,
                        )
                        or False
                    ),
                    "new_value_datetime": (
                        new_value
                        and datetime.strftime(
                            datetime.combine(
                                datetime.strptime(new_value, tools.DEFAULT_SERVER_DATE_FORMAT),
                                datetime.min.time(),
                            ),
                            tools.DEFAULT_SERVER_DATETIME_FORMAT,
                        )
                        or False
                    ),
                }
            )
        elif col_info["type"] == "boolean":
            values.update({"old_value_integer": initial_value, "new_value_integer": new_value})
        elif col_info["type"] == "selection":
            col_dict = dict(col_info["selection"])
            values.update(
                {
                    "old_value_char": initial_value and col_dict.get("initial_value", ""),
                    "new_value_char": new_value and col_dict.get("new_value", ""),
                }
            )
        elif col_info["type"] == "many2one":
            values.update(
                {
                    "old_value_integer": initial_value and initial_value.id or 0,
                    "new_value_integer": new_value and new_value.id or 0,
                    "old_value_char": initial_value and initial_value.name_get()[0][1] or "",
                    "new_value_char": new_value and new_value.name_get()[0][1] or "",
                }
            )
        else:
            tracked = False

        if tracked:
            return values
        return {}
