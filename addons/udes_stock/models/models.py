"""Base model enhancements"""

from odoo import models, api, _
from lxml import etree


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
