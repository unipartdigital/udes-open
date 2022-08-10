"""Base model enhancements"""

from odoo import models, api, _
from lxml import etree
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
from datetime import datetime
from odoo.exceptions import UserError


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

         On Core _create method vals are expected to be a dict
         """
        if isinstance(vals, dict):
            self.validate_values_of_date_fields(vals)
        res = super()._create(vals)
        return res

    @api.multi
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
            key: value for key, value in self._fields.items() if
            value.type in ("date", "datetime") and key not in ("write_date", "create_date")
        }
        date_values = {k: v for k, v in values.items() if
                       k in date_fields and isinstance(v, str) and len(v) >= 10}
        for date_value in date_values.values():
            try:
                date_field = datetime.strptime(date_value[:10], DATE_FORMAT)
            except:
                raise UserError(
                    _("Date '%s' is not valid.") % date_value
                )
            if date_field.year < 1000:
                raise UserError(
                    _("Date '%s' is not valid.") % date_value
                )
