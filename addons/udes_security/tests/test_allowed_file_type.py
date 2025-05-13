import base64
import contextlib
import logging
import pathlib
import sys
from unittest import mock

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.modules.module import get_resource_from_path, get_resource_path
from odoo.tests import common, tagged
from odoo.tools import mute_logger

from odoo.addons.udes_common.tests.common import SavepointMixin
from odoo.addons.udes_common.tools import RelFieldOps


@tagged("post_install", "-at_install")
class TestIrAttachment(common.SavepointCase, SavepointMixin):
    """
    Check that only the admin user can manage allowed file types and that downloads are blocked
    for non-admin users when trying to download files with a file type that is not allowed
    """

    @classmethod
    def setUpClass(cls):
        """
        Create allowed file type and attachments for blocked/unblocked files
        """
        super(TestIrAttachment, cls).setUpClass()

        cls.AllowedFileType = cls.env["udes.allowed_file_type"]
        cls.MimeType = cls.env["udes.mimetypes"]

        cls.allowed_file_type_csv = cls.env.ref("udes_security.udes_allowed_file_type_csv")
        cls.allowed_file_type_rtf = cls.env.ref("udes_security.udes_allowed_file_type_rtf")
        cls.allowed_file_type_txt = cls.env.ref("udes_security.udes_allowed_file_type_txt")
        cls.allowed_file_type_json = cls.env.ref("udes_security.udes_allowed_file_type_json")

        # Set these files to active
        cls.allowed_file_type_csv.active = True
        cls.allowed_file_type_rtf.active = True
        cls.allowed_file_type_txt.active = True
        cls.allowed_file_type_json.active = True

        cls.atch_txt_file = cls.create_attachment("text_file.txt")
        cls.atch_csv_file = cls.create_attachment("spreadsheet_file.csv")
        cls.atch_rtf_file = cls.create_attachment("rtf_file.rtf")
        cls.atch_html_file = cls.create_attachment("web_page.html")

        cls.new_user = cls.create_user("test_user", "test_user_login")

    @classmethod
    def create_user(cls, name, login, **kwargs):
        """Create and return a user - lifted from stock"""
        User = cls.env["res.users"]
        # Creating user without company
        # takes company from current user
        vals = {"name": name, "login": login}
        vals.update(kwargs)
        user = User.create(vals)

        # some action require email setup even if the email is not really sent
        user.partner_id.email = login

        return user

    @classmethod
    def _get_file_path(cls, filename):
        """Get file path from supplied filename"""
        module_file = sys.modules[cls.__module__].__file__
        module = get_resource_from_path(module_file)[0]
        files_path_str = get_resource_path(module, "tests", "files")
        files_path = pathlib.Path(files_path_str)
        file_path = files_path.joinpath(filename)

        return file_path

    @classmethod
    def create_attachment(cls, filename, user=None, **kwargs):
        """
        Create attachment from supplied filename.

        Optionally specify user and additional values for the attachment.
        """
        IrAttachment = cls.env["ir.attachment"]

        if user:
            IrAttachment = IrAttachment.with_user(user)

        file_path = cls._get_file_path(filename)

        attachment = IrAttachment.create(
            {"name": file_path.name, "datas": base64.b64encode(file_path.read_bytes()), **kwargs}
        )
        return attachment

    @classmethod
    def update_attachment(cls, attachment, filename, user=None, **kwargs):
        """
        Update attachment data from supplied filename.

        Optionally specify user and additional values for the attachment.
        """
        file_path = cls._get_file_path(filename)
        if user:
            attachment = attachment.with_user(user)
        res = attachment.write(
            {"name": file_path.name, "datas": base64.b64encode(file_path.read_bytes()), **kwargs}
        )
        # Need to manually trigger recompute due to how computed fields are handled in SavepointCase
        attachment.recompute()
        return res

    @classmethod
    def create_allowed_file_type(cls, file_type, mimetype, **kwargs):
        """Create allowed file type record from supplied file type"""
        mimetype_instance = cls.MimeType.create({"mimetype": mimetype})
        allowed_file_type_vals = {
            "name": file_type,
            "mimetype_ids": [(RelFieldOps.Replace, False, [mimetype_instance.id])],
        }
        allowed_file_type_vals.update(kwargs)

        allowed_file_type = cls.AllowedFileType.create(allowed_file_type_vals)

        return allowed_file_type

    def test_unblock_files_when_creating_active_filetype(self):
        """Assert that creating a file type unblocks those files"""
        self.assertFalse(self.atch_html_file.active)
        # Create HTML allowed file type record, unblocking HTML files
        self.create_allowed_file_type("html", "text/html")
        self.assertTrue(self.atch_html_file.active)

    def test_attachments_get_blocked_with_inactive_file_types(self):
        """Assert that when a file type becomes inactive the attachment is blocked"""
        self.assertTrue(self.allowed_file_type_csv.active)
        self.atch_csv_file.active = True
        self.assertTrue(self.atch_csv_file.active)

        # Set CSV allowed file type to inactive, blocking CSV files
        self.allowed_file_type_csv.active = False
        self.assertFalse(self.allowed_file_type_csv.active)
        self.assertFalse(self.atch_csv_file.active)

    def test_attachments_get_blocked_with_deleted_file_types(self):
        """Assert that when a file type is deleted the attachment is blocked"""
        AllowedFileType = self.env["udes.allowed_file_type"]

        self.assertTrue(self.allowed_file_type_rtf.active)
        self.atch_rtf_file.active = True
        self.assertTrue(self.atch_rtf_file.active)

        # Delete RTF allowed file type record, blocking RTF files
        self.allowed_file_type_rtf.unlink()
        self.assertFalse(self.atch_rtf_file.active)
        self.assertFalse(AllowedFileType.search([("name", "=", "rtf")]))

    def test_allowed_file_type_unique(self):
        """Assert that only one blocked file type record can exist for each file type"""
        # Create another allowed file type for csv and assert that an Integrity Error is raised
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.create_allowed_file_type(self.allowed_file_type_csv.name, "text/csv")

    def test_allowed_file_type_name_change_prevented(self):
        """Assert that the file type (aka name) on an allowed file type record cannot be changed"""
        with self.assertRaises(UserError):
            self.allowed_file_type_csv.name = "other_file_type"

    def test_formats_allowed_file_type_names(self):
        """
        Assert that file type name is properly formatted,
        i.e. lowercase with full stop character removed
        """
        json_file_type = "json"
        json_unformatted_file_types = ("JSON", ".json", ".JSON")

        # Ensure that _format_name properly formats each unformatted file type
        for file_type in json_unformatted_file_types:
            with self.subTest(file_type=file_type):
                self.assertEqual(self.AllowedFileType._format_name(file_type), json_file_type)

    def test_sets_attachment_file_type(self):
        """
        Assert that the file type is properly set on attachment and is
        updated when the file changes. Check it preserves the state of
        that file type.
        """
        self.allowed_file_type_json.active = False
        self.atch_csv_file.active = True
        self.assertEqual(self.atch_csv_file.u_file_type, "csv")

        # Replace csv file on csv attachment with a json file and check file type is updated
        self.update_attachment(self.atch_csv_file, "json_file.json")
        self.assertEqual(self.atch_csv_file.u_file_type, "json")
        self.assertFalse(self.atch_csv_file.active)

    def test_cannot_change_attachment_file_type_to_invalid_one(self):
        """Assert that the file type cannot be changed to an invalid one"""
        self.assertTrue(self.allowed_file_type_csv.active)
        self.assertEqual(self.atch_csv_file.u_file_type, "csv")

        # Replace csv file on csv attachment with a html file and check error is raised
        # Also try manually setting the attachment to active
        with self.assertRaises(UserError):
            self.update_attachment(
                self.atch_csv_file.with_env(self.env(user=self.new_user)),
                "web_page.html",
                user=self.new_user,
                active=True,
            )

        # Ensure file is still csv
        self.assertEqual(self.atch_csv_file.u_file_type, "csv")

    def test_active_not_manually_set(self):
        """
        When updating the attachment to active, check the attachment remains inactive
        if the file type is blocked
        """
        self.assertFalse(self.atch_html_file.active)
        # Manually making the attachment active
        self.atch_html_file.active = True
        self.assertFalse(self.atch_html_file.active)

        # Manually making the attachment active with context applied to skip active check
        self.atch_html_file.with_context(skip_active_check=True).write({"active": True})
        self.assertFalse(self.atch_html_file.active)

        # Updating filename as well as trying to make the attachment active
        self.atch_html_file.write({"active": True, "name": "test.html"})
        self.assertEqual(self.atch_html_file.name, "test.html")
        self.assertFalse(self.atch_html_file.active)

    def test_unprivileged_user_can_upload_allowed_file_types(self):
        """The system will permit uploads of permitted file types by unprivileged users."""
        allowed_files = [
            ("bmp", "image/bmp"),
            ("csv", "text/csv"),
            ("doc", "application/msword"),
            ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("gif", "image/gif"),
            ("jpeg", "image/jpeg"),
            ("jpg", "image/jpeg"),
            ("json", "application/json"),
            ("ods", "application/vnd.oasis.opendocument.spreadsheet"),
            ("odt", "application/vnd.oasis.opendocument.text"),
            ("pdf", "application/pdf"),
            ("png", "image/png"),
            ("rtf", "application/rtf"),
            ("tif", "image/tiff"),
            ("tiff", "image/tiff"),
            ("txt", "text/plain"),
            ("xls", "application/vnd.ms-excel"),
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("xml", "application/xml"),
        ]
        for ext, mimetype in allowed_files:
            with self.subTest(ext=ext, mimetype=mimetype), self.savepoint():
                att = self.create_attachment(
                    f"test-user-upload.{ext}", mimetype=mimetype, user=self.new_user
                )
                self.assertEqual(att.u_file_type, ext)
                self.assertTrue(att.active)

    def test_accepts_secondary_mime_subtype(self):
        """The system will accept user-provided mimetypes."""
        # TODO: add the secondary mime subtype to allowed file types.
        mimetype_instance = self.MimeType.create({"mimetype": "text/plane"})
        self.allowed_file_type_txt.write(
            {"mimetype_ids": [(RelFieldOps.Add, mimetype_instance.id, 0)]}
        )

        # Mock out Odoo's guess mimetype because it's too good at guessing
        # mimetypes ...
        with mock.patch("odoo.addons.udes_security.models.ir_attachment.guess_mimetype") as gm:
            gm.return_value = None
            att = self.create_attachment(
                "secondary-test.txt", mimetype="text/plane", user=self.new_user
            )
            self.assertEqual(att.u_file_type, "txt")
            self.assertTrue(att.active)
        gm.assert_called()

    def test_raises_on_unrelated_mimetype(self):
        """The system will raise an error if the provided mimetype is not associated with the file type."""
        expected_error_message = "Mimetype 'text/plane' is not associated with file type 'txt'"
        with (
            self.assertRaisesRegex(UserError, expected_error_message, msg=expected_error_message),
            mock.patch("odoo.addons.udes_security.models.ir_attachment.guess_mimetype") as gm,
        ):
            gm.return_value = None
            self.create_attachment("secondary-test.txt", mimetype="text/plane", user=self.new_user)
        gm.assert_called()

    def test_raises_on_change_to_unrelated_mimetype(self):
        """The system will raise an error if the changed mimetype is not associated with the file type."""
        expected_error_message = "Mimetype 'text/plane' is not associated with file type 'txt'"
        attachment = self.create_attachment(
            "secondary-test.txt", mimetype="text/plain", user=self.new_user
        )
        with (
            self.assertRaisesRegex(UserError, expected_error_message, msg=expected_error_message),
            mock.patch("odoo.addons.udes_security.models.ir_attachment.guess_mimetype") as gm,
        ):
            gm.return_value = None
            self.update_attachment(
                attachment, "secondary-test.txt", mimetype="text/plane", user=self.new_user
            )
        gm.assert_called()

    def test_raises_on_direct_change_to_unrelated_mimetype(self):
        """The system will raise an error if the changed mimetype is not associated with the file type."""
        expected_error_message = "Mimetype 'text/plane' is not associated with file type 'txt'"
        attachment = self.create_attachment(
            "secondary-test.txt", mimetype="text/plain", user=self.new_user
        )
        with self.assertRaisesRegex(UserError, expected_error_message, msg=expected_error_message):
            attachment.mimetype = "text/plane"

    def test_logs_details_of_unrelated_mimetype(self):
        """The system will log a message for unrelated mimetypes."""
        expected_message = (
            f"User {self.new_user.id} tried to upload file 'secondary-test.txt' "
            "with file type 'txt' and unrelated mimetype 'text/plane'"
        )
        attachment = self.create_attachment(
            "secondary-test.txt", mimetype="text/plain", user=self.new_user
        )
        with (
            contextlib.suppress(UserError),
            self.assertLogs("odoo.addons.udes_security.models.ir_attachment", logging.INFO) as cm,
        ):
            attachment.mimetype = "text/plane"
        messages = [r.getMessage() for r in cm.records]

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], expected_message)


@tagged("post_install", "-at_install")
class TestAllowedFileType(common.SavepointCase):
    """Tests specific to the AllowedFileType model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AllowedFileType = cls.env["udes.allowed_file_type"]

        cls.allowed_file_type_csv = cls.env.ref("udes_security.udes_allowed_file_type_csv")
        cls.allowed_file_type_csv.active = True

    def test_is_file_type_allowed(self):
        """The system can determine whether a filetype is allowed."""
        self.assertTrue(self.AllowedFileType.is_allowed("csv"))

    def test_is_file_type_not_allowed(self):
        """The system can determine whether a filetype is allowed."""
        self.allowed_file_type_csv.active = False
        self.assertFalse(self.AllowedFileType.is_allowed("csv"))

    def test_exists_mimetype_association(self):
        """The system can determine whether a mime type is associated with a file type."""
        self.assertTrue(self.AllowedFileType.exists_mimetype_association("txt", "text/plain"))

    def test_not_exists_mimetype_association(self):
        """The system can determine whether a mime type is associated with a file type."""
        self.assertFalse(self.AllowedFileType.exists_mimetype_association("txt", "text/plane"))

    def test_extracts_type_from_filename(self):
        """The system can get the file type name from a filename."""
        filename = "foo.txt"
        self.assertEqual(self.AllowedFileType.get_type_name_from_file_name(filename), "txt")

    def test_returns_empty_string_as_type_name_of_extensionless_filename(self):
        """The system will return an empty string for filenames without extension."""
        filename = "foo"
        self.assertEqual(self.AllowedFileType.get_type_name_from_file_name(filename), "")

    def test_downcases_type_name(self):
        """The system will return type names in lower case."""
        filename = "foo.TXT"
        self.assertEqual(self.AllowedFileType.get_type_name_from_file_name(filename), "txt")
