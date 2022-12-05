from lxml import etree

from odoo import models, api
from odoo.osv.orm import setup_modifiers


class BaseModel(models.AbstractModel):
    _inherit = "base"

    @api.multi
    def write(self, vals):
        """Inherit write to add a check against res.archiving.restriction
        when the active field is written to.
        """
        ResArchivingRestriction = self.env["res.archiving.restriction"]
        if "active" in vals:
            ResArchivingRestriction._check_can_archive(self._name)
        return super().write(vals)

    @api.model
    def fields_view_get(self, view_id=None, view_type="form", toolbar=False, submenu=False):
        """Override to remove buttons/editable functionality for view only desktop users
        and take into account archiving restrictions for the given user"""

        def _add_confirmation_warning_on_toggle_active(doc):
            """Add confirm attribute on toggle_active button"""
            nodes = doc.xpath("//button[@name='toggle_active']")
            confirm_message = "Are you sure you want to modify this record? " \
                              "If Archived, it will become unavailable and hidden from searches. " \
                              "If Unarchived, it will become available and included in searches. "
            for node in nodes:
                node.attrib["confirm"] = confirm_message
                setup_modifiers(node, {})
            return bool(nodes)

        def _remove_active(doc):
            """Remove any field or smart button related to the active field from the doc"""
            for node in doc.xpath("//button[@name='toggle_active']"):
                node.getparent().remove(node)
            for node in doc.xpath("//field[@name='active']"):
                node.getparent().remove(node)

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

        ResArchivingRestriction = self.env["res.archiving.restriction"]
        ModelException = self.env["udes.readonly_desktop_user_model_exception"].sudo()

        res = super().fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )

        model = res.get("model", False)
        doc = etree.XML(res["arch"])
        if self.env.user.u_desktop_readonly and not ModelException.is_exempt(model):
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
            res["readonly_desktop_user"] = True  # Used in basic_view.js
        elif not ResArchivingRestriction._get_can_archive(model):
            if doc.tag == "form":
                _remove_active(doc)
                res["arch"] = etree.tostring(doc)
            res["cannot_archive_record"] = True  # Used in basic_view.js
        elif doc.tag == "form":
            toggle_active_updated = _add_confirmation_warning_on_toggle_active(doc)
            if toggle_active_updated:
                res["arch"] = etree.tostring(doc)
        return res
