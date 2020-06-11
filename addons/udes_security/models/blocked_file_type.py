# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BlockedFileType(models.Model):
    """
    Blocked file type which the user is prevented from uploading or downloading
    """

    _name = "udes.blocked_file_type"
    _description = "Blocked File Type"
    _order = "name"

    _sql_constraints = [("name_uniq", "unique (name)", "The File Type must be unique")]

    name = fields.Char("File Type", required=True, index=True)
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
        """Set active field on attachments that match the supplied blocked file types"""
        IrAttachment = self.env["ir.attachment"]

        attachments_to_set_active = IrAttachment.browse()
        attachments_to_set_inactive = IrAttachment.browse()

        for blocked_file_type in self:
            is_blocked_file_type = blocked_file_type.active

            # If a blocked file type record is being deleted then it should be treated as inactive
            if deleted:
                is_blocked_file_type = False

            attachment_search_args = [("datas_file_type", "=", blocked_file_type.name)]

            attachments = IrAttachment.with_context(active_test=False).search(
                attachment_search_args
            )

            if not is_blocked_file_type:
                attachments_to_set_active += attachments
            else:
                attachments_to_set_inactive += attachments

        attachments_to_set_active.with_context(skip_active_check=True).write({"active": True})
        attachments_to_set_inactive.with_context(skip_active_check=True).write({"active": False})

        return True

    def _set_inactive_attachments_active_from_file_types(self, file_types):
        """Set active field to True for attachments that are in the file_types list"""
        IrAttachment = self.env["ir.attachment"]

        attachment_search_args = [
            ("datas_file_type", "in", file_types),
            ("active", "=", False),
        ]
        attachments = IrAttachment.search(attachment_search_args)
        attachments.with_context(skip_active_check=True).write({"active": True})

        return True

    @api.model
    def create(self, vals):
        """Override to ensure name is formatted correctly
           and relevant attachments are set to active/inactive"""
        formatted_vals = self._format_vals(vals)
        vals.update(formatted_vals)

        blocked_file_type = super(BlockedFileType, self).create(vals)
        blocked_file_type._update_attachments_active_status()

        return blocked_file_type

    @api.multi
    def write(self, vals):
        """Override to ensure name cannot be changed
           and relevant attachments are set to active/inactive"""
        if "name" in vals:
            raise UserError(_("Cannot change File Type, please create a new record instead."))

        res = super(BlockedFileType, self).write(vals)

        if "active" in vals:
            self._update_attachments_active_status()

        return res

    @api.multi
    def unlink(self):
        """Set attachments with same file type to active if needed"""
        file_types = self.mapped("name")

        res = super(BlockedFileType, self).unlink()

        self._set_inactive_attachments_active_from_file_types(file_types)

        return res
