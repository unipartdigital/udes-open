import html
import logging
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from PIL import Image
import base64
import mimetypes
from odoo.tools.mimetypes import guess_mimetype # Uses python-magic to guess mimetype

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.depends("mimetype")
    def _compute_file_type(self):
        """Set file type from mimetype"""
        for attachment in self:
            mimetype = attachment.mimetype or ""
            attachment.u_file_type = self._get_file_type(mimetype)

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
    def _get_file_type(self, mimetype):
        """Get file type from supplied mimetype"""
        file_type = ""

        if "/" in mimetype:
            file_type = mimetype.split("/")[-1].lower()

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
        """Extend to escape filename and remove exif data from images"""
        allowed_image_file_types = ["jpg", "jpeg", "png", "webp"]
        checked_vals_list = []
        for vals in vals_list:
            if "name" in vals:
                vals = self._check_contents(vals)
            checked_vals_list.append(vals)
        attachments = super().create(checked_vals_list)
        for attachment in attachments.filtered(
                lambda att: att.u_file_type in allowed_image_file_types
        ):
            attachment.datas = attachment.with_context(skip_remove_exif=True)._remove_exif_data(
                attachment.datas
            )
        return attachments

    def _remove_exif_data(self, datas):
        # Load the image using PIL
        image = Image.open(io.BytesIO(base64.b64decode(datas)))

        # Save the image without metadata
        output = io.BytesIO()
        image.save(output, format=image.format)
        return base64.b64encode(output.getvalue())

    def write(self, vals):
        """Extend to escape filename"""
        allowed_image_mimetypes = ["image/jpg", "image/jpeg", "image/png", "image/webp"]
        if "name" in vals:
            vals = self._check_contents(vals)

        if "active" in vals and not self.env.context.get("skip_active_check"):
            # Prevent user from manually setting attachment to active/inactive
            del vals["active"]
        if (
            "datas" in vals
            and "mimetype" in vals
            and vals["mimetype"] in allowed_image_mimetypes
            and not self.env.context.get("skip_remove_exif")
        ):
            vals["datas"] = self._remove_exif_data(vals["datas"])
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

    def _compute_mimetype(self, values):
        """
        Override core _compute_mimetype by checking first the content, if not found from file
        content checking from name or url as in odoo core _compute_mimetype method.
        """
        # Compute mimetype from content of the file
        raw = None
        mimetype = False
        if values.get('raw'):
            raw = values['raw']
        elif values.get('datas'):
            raw = base64.b64decode(values['datas'])
        if raw:
            mimetype = guess_mimetype(raw)
        # guess_mimetype checks the content of the file by using python-magic library.
        if not mimetype or mimetype == "application/octet-stream":
            # In general python-magic finds the file format, if not found try finding from filename.
            mimetype = False
            if values.get("mimetype"):
                mimetype = values['mimetype']
            if not mimetype and values.get("name"):
                mimetype = mimetypes.guess_type(values["name"])[0]
            if not mimetype and values.get("url"):
                mimetype = mimetypes.guess_type(values["url"])[0]
        return mimetype or "application/octet-stream"
