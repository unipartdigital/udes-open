import html
import logging
import io
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from PIL import Image
import base64
import mimetypes
from odoo.tools.mimetypes import guess_mimetype  # Uses python-magic to guess mimetype

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.depends("name")
    def _compute_file_type(self):
        """Set file type from mimetype"""
        AllowedFileType = self.env["udes.allowed_file_type"]

        for attachment in self:
            filename = attachment.name or ""
            attachment.u_file_type = AllowedFileType.get_type_name_from_file_name(filename)

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

    @api.constrains("u_file_type", "active", "mimetype")
    def _check_file_type(self):
        """
        If file type is blocked raise an error, if the user isn't superuser or admin.

        Active field watched to ensure that blocked files cannot manually be made active.
        """
        AllowedFileType = self.env["udes.allowed_file_type"]

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
            if (
                active
                and attachment.u_file_type
                and not AllowedFileType.exists_mimetype_association(
                    attachment.u_file_type, attachment.mimetype
                )
            ):
                _logger.info(
                    _(
                        "User %d tried to upload file %r with file type %r and unrelated mimetype %r"
                    ),
                    self.env.uid,
                    attachment.name,
                    attachment.u_file_type,
                    attachment.mimetype,
                )
                error_msg = "Mimetype %r is not associated with file type %r"
                raise UserError(_(error_msg) % (attachment.mimetype, attachment.u_file_type))

            if active != attachment.active:
                # Set file to active/inactive depending on file type
                attachment.with_context(skip_active_check=True).write({"active": active})

    @api.model_create_multi
    def create(self, vals_list):
        """Extend to escape filename and remove exif data from images"""
        allowed_image_mimetypes = ["image/jpg", "image/jpeg", "image/png", "image/webp"]

        checked_vals_list = []
        for vals in vals_list:
            if "name" in vals:
                vals = self._check_contents(vals)
            checked_vals_list.append(vals)
            if vals.get("url", False):
                # Restrict URLs to relative paths (starting with "/") or HTTPS (starting with "https://")
                # This ensures only safe URL types are allowed, preventing schemes like "file://" or "sftp://"
                # from bypassing security checks.
                if not (vals["url"].startswith("/") or vals["url"].startswith("https://")):
                    # Raise an error if URL is not a valid type
                    raise UserError(
                        "Invalid URL: Only secure HTTPS links or relative URLs (starting with '/') are allowed for images. Please update the URL format and try again."
                    )
                if "mimetype" in vals and vals["mimetype"] in allowed_image_mimetypes:
                    # Process URL-based image, convert to binary and remove EXIF data
                    vals["datas"] = self._process_url_image(vals["url"])
                    vals["name"] = self._extract_filename_from_url(vals["url"])
                    vals["url"] = False  # Set URL to False as it's now stored in binary
                    vals["type"] = "binary"  # Change type to 'binary' to reflect new storage format

        attachments = super().create(checked_vals_list)
        for attachment in attachments.filtered(lambda att: att.mimetype in allowed_image_mimetypes):
            if attachment.datas:
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

    def _process_url_image(self, url):
        """Fetch an image from the URL and convert it to binary"""
        response = requests.get(url, stream=True)
        response.raise_for_status()

        image_data = base64.b64encode(response.raw.read())
        return image_data

    def _extract_filename_from_url(self, url):
        """Extract a filename from the URL"""
        filename = url.split("/")[-1]
        return filename if filename else "image.jpg"

    def write(self, vals):
        """Extend to escape filename"""
        allowed_image_mimetypes = ["image/jpg", "image/jpeg", "image/png", "image/webp"]
        # If we update the url - recompute the mimetype,
        # as we may need to download it to sanitise if it has been changed to an image.
        if "name" in vals or "url" in vals:
            vals = self._check_contents(vals)

        if "active" in vals and not self.env.context.get("skip_active_check"):
            # Prevent user from manually setting attachment to active/inactive
            del vals["active"]

        if vals.get("url", False):
            # Restrict URLs to relative paths (starting with "/") or HTTPS (starting with "https://")
            # This ensures only safe URL types are allowed, preventing schemes like "file://" or "sftp://"
            # from bypassing security checks.
            if not (vals["url"].startswith("/") or vals["url"].startswith("https://")):
                # Raise an error if URL is not a valid type
                raise UserError(
                    "Invalid URL: Only secure HTTPS links or relative URLs are allowed. Please update the URL format and try again."
                )
            if "mimetype" in vals and vals["mimetype"] in allowed_image_mimetypes:
                # Process URL-based image, convert to binary and remove EXIF data
                vals["datas"] = self._process_url_image(vals["url"])
                vals["name"] = self._extract_filename_from_url(vals["url"])
                vals["url"] = False  # Set URL to False as it's now stored in binary
                vals["type"] = "binary"  # Change type to 'binary' to reflect new storage format

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

        # If is superuser compute mimetype as it was computed on core odoo, checking the extension
        # before, for the reason that odoo core js and css files where created with mimetype
        # text/plain which was bringing error on load of udes. With this change trying to check for
        # file contents first when uploaded files are done from users and not when are uploaded from
        # superusers.
        if self.env.user._is_superuser():
            return super()._compute_mimetype(values)
        # Compute mimetype from content of the file when is not ran by superuser first,
        # later extension if not found from contents.
        raw = None
        mimetype = False
        if values.get("raw"):
            raw = values["raw"]
        elif values.get("datas"):
            raw = base64.b64decode(values["datas"])
        if raw:
            mimetype = guess_mimetype(raw)
        # guess_mimetype checks the content of the file by using python-magic library.
        if not mimetype or mimetype == "application/octet-stream":
            # In general python-magic finds the file format, if not found try finding from filename.
            mimetype = False
            if values.get("mimetype"):
                mimetype = values["mimetype"]
            if not mimetype and values.get("name"):
                mimetype = mimetypes.guess_type(values["name"])[0]
            if not mimetype and values.get("url"):
                mimetype = mimetypes.guess_type(values["url"])[0]
        return mimetype or "application/octet-stream"
