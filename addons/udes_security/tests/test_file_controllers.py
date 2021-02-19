import base64
import json
import pathlib
import sys

from contextlib import contextmanager

from odoo.exceptions import UserError
from odoo.modules.module import get_resource_from_path, get_resource_path
from odoo.tests import common


@common.at_install(False)
@common.post_install(True)
class TestFileControllers(common.HttpCase):
    """Check that blocked file types cannot be uploaded or downloaded by non-admin users"""

    def setUp(self):
        """
        Use test cursor for environment
        Create allowed file types and blocked/unblocked attachments
        Create user for testing controllers as non-admin
        """
        super().setUp()

        # Use default test cursor for default environment
        def restore(cr=self.cr, env=self.env):
            """
            Based on workaround from print module
            Restore original cursor and environment once changes made with test cursor
            """
            self.env = env
            self.cr = cr

        self.cr = self.registry.cursor()
        self.env = self.env(self.cr)
        self.addCleanup(restore)

        ResUsers = self.env["res.users"]

        self.test_user_login = "test_user"
        self.test_user_pwd = "7estUserPassword!"

        self.test_user = ResUsers.create({"name": "Test User", "login": self.test_user_login})
        self.test_user.password = self.test_user_pwd

        self.allowed_file_type_txt = self.env.ref("udes_security.udes_allowed_file_type_txt")
        self.allowed_file_type_json = self.env.ref("udes_security.udes_allowed_file_type_json")

        # Set TXT and JSON allowed file types to inactive, so they are blocked for the tests
        self.allowed_file_type_txt.active = False
        self.allowed_file_type_json.active = False

        self.atch_txt_file = self.create_attachment("text_file.txt")
        self.atch_csv_file = self.create_attachment("spreadsheet_file.csv")

        # Run tests as the test user
        self.authenticate(self.test_user_login, self.test_user_pwd)

    @contextmanager
    def release(self):
        """
        Workaround from print module to temporarily release test cursor
        """

        # Commit so that any changes are visible to external threads
        self.cr.commit()

        # Release thread's cursor lock
        self.cr.release()

        try:
            # Allow external threads to use the cursor
            yield

        finally:
            # Reacquire thread's cursor lock
            self.cr.acquire()

            # Flush cache so that external changes are picked up
            self.env.clear()

    def url_open(self, *args, **kwargs):
        with self.release():
            return super().url_open(*args, **kwargs)

    def _get_file_path(self, filename):
        """Get file path from supplied filename"""
        module_file = sys.modules[self.__module__].__file__
        module = get_resource_from_path(module_file)[0]
        files_path_str = get_resource_path(module, "tests", "files")
        files_path = pathlib.Path(files_path_str)
        file_path = files_path.joinpath(filename)

        return file_path

    def _get_attachment_download_url(self, attachment):
        return "/web/content/%s?download=true" % (attachment.id)

    def create_attachment(self, filename, user=False):
        """Create attachment from supplied filename"""
        IrAttachment = self.env["ir.attachment"]

        # Create attachment as specifc user, if specified
        if user:
            IrAttachment = IrAttachment.sudo(user)

        file_path = self._get_file_path(filename)

        attachment = IrAttachment.create(
            {
                "name": file_path.name,
                "datas_fname": file_path.name,
                "datas": base64.b64encode(file_path.read_bytes()),
            }
        )

        return attachment

    def create_allowed_file_type(self, file_type, **kwargs):
        """Create allowed file type from supplied file type"""
        AllowedFileType = self.env["udes.allowed_file_type"]

        allowed_file_type_vals = {"name": file_type}
        allowed_file_type_vals.update(kwargs)

        allowed_file_type = AllowedFileType.create(allowed_file_type_vals)

        return allowed_file_type

    def test_assert_blocked_file_type_download_restricted(self):
        """Assert blocked file type download prevented for test user"""
        csv_file_url = self._get_attachment_download_url(self.atch_csv_file)
        txt_file_url = self._get_attachment_download_url(self.atch_txt_file)

        # Attempt to download unblocked .csv attachment
        # Should be able to download the file as CSV files are allowed
        csv_response = self.url_open(csv_file_url)
        self.assertEquals(csv_response.text, "Type,Testing\nSpreadsheet,Y\n")

        # Attempt to download blocked .txt attachment
        # Should get a message back saying the file type is not allowed
        txt_response = self.url_open(txt_file_url)
        txt_response_message = json.loads(txt_response.content)["message"]
        self.assertEquals(txt_response_message, "Unable to download file: File type blocked")

    def test_assert_blocked_file_type_upload_restricted(self):
        """Assert blocked file type upload prevented for test user"""
        # Should be able to upload rtf file as it is not a blocked file type
        self.create_attachment("rtf_file.rtf", user=self.test_user)

        # Should not be able to upload json file as it is a blocked file type
        with self.assertRaises(UserError):
            self.create_attachment("json_file.json", user=self.test_user)
