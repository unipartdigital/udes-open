# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError


class AllowedFileType(models.Model):
    """
    Allowed file type which the user can upload and download
    """

    _name = "udes.allowed_file_type"
    _description = "Allowed File Type"
    _order = "name"

    _sql_constraints = [("name_uniq", "unique (name)", "The File Type must be unique")]

    name = fields.Char(
        "File Type",
        required=True,
        index=True,
        help="The file extension that is allowed to be uploaded and downloaded by users",
    )
    description = fields.Char("Description")
    active = fields.Boolean("Active?", default=True)

    def _format_name(self, name):
        """Convert supplied name to lowercase if needed"""
        formatted_name = name.lower().replace(".", "") if name else ""
        return formatted_name

    def _format_vals(self, vals):
        """Format the required values in the supplied dictionary and
        return the updated values"""
        formatted_vals = {}

        name = vals.get("name", "")
        if name:
            name = self._format_name(name)
            formatted_vals["name"] = name

        return formatted_vals

    def _update_attachments_active_status(self, deleted=False):
        """Set active field on attachments that match the supplied allowed file types"""
        IrAttachment = self.env["ir.attachment"]

        attachments_to_set_active = IrAttachment.browse()
        attachments_to_set_inactive = IrAttachment.browse()

        for allowed_file_type in self:
            is_allowed_file_type = allowed_file_type.active

            # If an allowed file type record is being deleted then it should be treated as inactive
            if deleted:
                is_allowed_file_type = False

            attachment_search_args = [("u_file_type", "=", allowed_file_type.name)]

            attachments = IrAttachment.with_context(active_test=False).search(
                attachment_search_args
            )

            if is_allowed_file_type:
                attachments_to_set_active += attachments
            else:
                attachments_to_set_inactive += attachments

        # Make active/inactive as superuser to avoid error about blocked file types
        # when a non-admin user with Manage Allowed File Types creates, archives or unarchives
        # an Allowed File Type record
        attachments_to_set_active.with_user(SUPERUSER_ID).with_context(
            skip_active_check=True
        ).write({"active": True})
        attachments_to_set_inactive.with_user(SUPERUSER_ID).with_context(
            skip_active_check=True
        ).write({"active": False})

        return True

    def _set_attachments_inactive_from_file_types(self, file_types):
        """Set active field to False for attachments that are in the file_types list"""
        IrAttachment = self.env["ir.attachment"]

        attachment_search_args = [("u_file_type", "in", file_types)]
        attachments = IrAttachment.search(attachment_search_args)
        # Make inactive as superuser to avoid error about blocked file types
        # when a non-admin user with Manage Allowed File Types deletes an Allowed File Type record
        attachments.with_user(SUPERUSER_ID).with_context(skip_active_check=True).write(
            {"active": False}
        )

        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Extend to ensure name is formatted correctly
        and relevant attachments are set to active/inactive
        """
        for vals in vals_list:
            formatted_vals = self._format_vals(vals)
            vals.update(formatted_vals)

        allowed_file_types = super().create(vals_list)
        allowed_file_types._update_attachments_active_status()

        return allowed_file_types

    def write(self, vals):
        """
        Extend to ensure name cannot be changed
        and relevant attachments are set to active/inactive
        """
        name = vals.get("name")
        if name:
            if len(self) == 1 and name == self.name:
                del vals["name"]
            else:
                raise UserError(_("Cannot change File Type, please create a new record instead."))

        res = super().write(vals)

        if "active" in vals:
            self._update_attachments_active_status()

        return res

    def unlink(self):
        """Set attachments with same file type to inactive if needed"""
        file_types = self.mapped("name")

        res = super().unlink()

        self._set_attachments_inactive_from_file_types(file_types)

        return res
