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
        """Return false if attachment file type is blocked, otherwise true"""
        BlockedFileType = self.env["udes.blocked_file_type"]

        active = True
        if attachment_type == "binary":
            blocked_file_type_domain = [("name", "=", file_type)]
            blocked_file_type_count = BlockedFileType.search_count(blocked_file_type_domain)

            if blocked_file_type_count:
                active = False

        return active

    @api.model
    def create(self, vals):
        """Override to set active to False if file type is blocked"""
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
