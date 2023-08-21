import html
import logging
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from PIL import Image

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.depends("name")
    def _compute_file_type(self):
        """Set file type from filename"""
        for attachment in self:
            filename = attachment.name or ""
            attachment.u_file_type = self._get_file_type(filename)

    u_file_type = fields.Char("File Type", compute="_compute_file_type", store=True)
    active = fields.Boolean(
        string="Active?",
        default=True,
        help="""If not set, the attachment is hidden from searches, 
        attachment widgets on other records etc.
        An attachment can only be set to active if its file type is allowed.
        """,
    )

    @api.model
    def _get_file_type(self, filename):
        """Get file type from supplied filename"""
        file_type = ""

        if "." in filename:
            file_type = filename.split(".")[-1].lower()

        return file_type

    @api.model
    def _get_file_type_allowed(self, file_type):
        """
        Returns True if the supplied file type is allowed on the system, otherwise False.

        If the file type is blank, it is considered allowed at this stage.
        """
        AllowedFileType = self.env["udes.allowed_file_type"]

        allowed = True
        if file_type:
            allowed_file_type_domain = [("name", "=", file_type)]
            allowed_file_type_count = AllowedFileType.search_count(allowed_file_type_domain)

            if not allowed_file_type_count:
                allowed = False

        return allowed

    def _check_contents(self, vals):
        """Extend to protect against XSS attacks"""
        filename = vals.get("name")
        if filename:
            vals["name"] = html.escape(filename, quote=True)

        return super()._check_contents(vals)

    @api.constrains("u_file_type", "active")
    def _check_file_type(self):
        """
        If file type is blocked raise an error, if the user isn't superuser or admin.

        Active field watched to ensure that blocked files cannot manually be made active.
        """
        for attachment in self:
            active = self._get_file_type_allowed(attachment.u_file_type)
            # If the attachment would not be active then the file type is blocked
            # Log message and raise exception if not superuser or admin
            if not active:
                if not self.env.user._is_superuser_or_admin():
                    _logger.info(
                        f"User {self.env.uid} tried to upload file '{attachment.name}' "
                        "which has a blocked file type"
                    )
                    raise UserError(
                        _(
                            """
                            Unable to upload attachment:
                            File type '%s' blocked by the system administrator.
                            """
                        )
                        % (attachment.u_file_type)
                    )

            if active != attachment.active:
                # Set file to active/inactive depending on file type
                attachment.with_context(skip_active_check=True).write({"active": active})

    @api.model_create_multi
    def create(self, vals_list):
        """Extend to escape filename"""
        for vals in vals_list:
            if "name" in vals:
                vals = self._check_contents(vals)
            if "attachment" in vals and "attachment_filename" in vals:
                processed_attachment_data = self._process_attachment_data(vals["attachment"])
                vals["attachment"] = processed_attachment_data
        return super().create(vals_list)

    def _process_attachment_data(self, attachment_data):
        # Check if the attachment is an image based on its file extension
        allowed_image_extensions = [".jpg", ".jpeg", ".png", ".webp"]

        attachment_name = attachment_data.name.lower()
        if any(attachment_name.endswith(ext) for ext in allowed_image_extensions):
            processed_data = self._remove_exif_data(attachment_data)
            return processed_data

        return attachment_data

    def _remove_exif_data(self, img):
        # Load the image using PIL
        image = Image.open(io.BytesIO(img))

        # Save the image without metadata
        output = io.BytesIO()
        image.save(output, format=image.format)

        return output.getvalue()

    def write(self, vals):
        """Extend to escape filename"""
        if "name" in vals:
            vals = self._check_contents(vals)

        if "active" in vals and not self.env.context.get("skip_active_check"):
            # Prevent user from manually setting attachment to active/inactive
            del vals["active"]

        return super().write(vals)

    @api.model
    def get_serve_attachment(self, url, extra_domain=None, extra_fields=None, order=None):
        """Extend to allowed inactive attachments to be served"""
        self = self.with_context(active_test=False)
        return super().get_serve_attachment(
            url, extra_domain=extra_domain, extra_fields=extra_fields, order=order
        )

    def _set_blocked_attachments_to_inactive(self):
        """
        Identify any active attachments with a file type that is not allowed
        and set them to inactive.

        This ensures that when udes_security is installed, any existing attachments that were
        created before the module was installed are now checked.
        """
        AllowedFileType = self.env["udes.allowed_file_type"]

        allowed_file_types = AllowedFileType.search([]).mapped("name")

        attachment_domain = [
            ("u_file_type", "!=", False),
            ("u_file_type", "not in", allowed_file_types),
        ]

        attachments_to_set_inactive = self.search(attachment_domain)
        attachments_to_set_inactive.write({"active": False})
