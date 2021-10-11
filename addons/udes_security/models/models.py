from lxml import etree

from odoo import models, api
from odoo.osv.orm import setup_modifiers


class BaseModel(models.AbstractModel):
    _inherit = "base"

    @api.model
    def fields_view_get(self, view_id=None, view_type="form", toolbar=False, submenu=False):
        """Override to remove buttons/editable functionality for view only desktop users"""

        def _remove_nodes(doc, xpath):
            """Remove any elements from the view that match the supplied xpath"""
            for node in doc.xpath(xpath):
                node.getparent().remove(node)

        def _remove_buttons(doc):
            """Remove all buttons from the view that have not been marked as an exception"""
            _remove_nodes(doc, "//button[not(@readonly_user_exception='1')]")

        def _set_fields_readonly(doc, res):
            """Set all fields in the view to readonly"""
            for node in doc.xpath("//field"):
                field_name = node.get("name")
                if field_name:
                    node.set("readonly", "1")
                    if field_name in res["fields"]:
                        setup_modifiers(node, res["fields"][field_name])

        ModelException = self.env["udes.readonly_desktop_user_model_exception"].sudo()

        res = super().fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )

        model = res.get("model", False)
        if self.env.user.u_desktop_readonly and not ModelException.is_exempt(model):
            doc = etree.XML(res["arch"])

            doc.set("create", "false")
            doc.set("edit", "false")
            doc.set("duplicate", "false")
            doc.set("delete", "false")

            if doc.tag == "form":
                _remove_buttons(doc)
                # Make all fields readonly
                # Readonly user shouldn't be able to get a form into edit mode, but it is possible
                # via the URL to bring up new record screen and quick create for relational fields
                _set_fields_readonly(doc, res)

            elif doc.tag == "tree":
                _remove_buttons(doc)
                _set_fields_readonly(doc, res)
                # Sequence handle allows records to be re-ordered
                _remove_nodes(doc, "//field[@widget='handle']")

            elif doc.tag == "kanban":
                doc.set("quick_create", "false")
                doc.set("draggable", "false")
                doc.set("deletable", "false")
                doc.set("editable", "false")
                doc.set("group_create", "false")
                doc.set("group_edit", "false")
                doc.set("group_delete", "false")
                doc.set("readonly_desktop_user", "true")

                _remove_nodes(doc, "//a[@type='action']")
                _remove_nodes(doc, "//ul[hasclass('oe_kanban_colorpicker')]")
                _remove_buttons(doc)
                _set_fields_readonly(doc, res)

            res["arch"] = etree.tostring(doc)
            # Remove archive option in tree view and make calendar readonly
            res["readonly_desktop_user"] = True

        return res
