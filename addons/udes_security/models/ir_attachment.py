# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.depends("datas_fname")
    def _compute_datas_file_type(self):
        """Set file type from file name"""
        for attachment in self:
            filename = attachment.datas_fname or ""
            attachment.datas_file_type = filename.split(".")[-1].lower()

    datas_file_type = fields.Char("File Type", compute="_compute_datas_file_type", store=True)
    active = fields.Boolean(string="Active?", default=True)

    def _get_active_value(self, attachment_type, file_type):
        """
        Determines whether the attachment record in self should be set to active or inactive.

        Attachment will be set to inactive if it meets the following criteria:

        1. Is a binary attachment
        2. Has a file type set
        3. File type is not set as allowed
        """
        AllowedFileType = self.env["udes.allowed_file_type"]

        active = True
        if attachment_type == "binary" and file_type:
            active_file_type_domain = [("name", "=", file_type)]
            active_file_type_count = AllowedFileType.search_count(active_file_type_domain)

            if not active_file_type_count:
                active = False

        return active

    @api.model
    def create(self, vals):
        """Override to set active to False if file type is not allowed"""
        attachment = super(IrAttachment, self).create(vals)

        # Check if the attachment file type is blocked
        # Raise exception if not superuser otherwise set to inactive
        active = self._get_active_value(attachment.type, attachment.datas_file_type)
        if not active:
            if self.env.uid != SUPERUSER_ID:
                raise UserError(
                    _("Unable to upload file: File type blocked by system administrator.")
                )
            else:
                attachment.with_context(skip_active_check=True).write({"active": False})

        return attachment

    @api.multi
    def write(self, vals):
        """Override to update active if file type is blocked/unblocked"""
        res = super(IrAttachment, self).write(vals)

        if not self.env.context.get("skip_active_check", False):
            for attachment in self:
                active = self._get_active_value(attachment.type, attachment.datas_file_type)
                if active != attachment.active:
                    # If the attachment would not be active then the file type is blocked
                    # Raise exception if not superuser
                    if not active:
                        if self.env.uid != SUPERUSER_ID:
                            raise UserError(
                                _(
                                    """Unable to upload attachment:
                                    File type blocked by system administrator."""
                                )
                            )

                    attachment.with_context(skip_active_check=True).write({"active": active})

        return res
