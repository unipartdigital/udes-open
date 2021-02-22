# -*- coding: utf-8 -*-

import base64
import pathlib
import sys

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.modules.module import get_resource_from_path, get_resource_path
from odoo.tests import common
from odoo.tools import mute_logger


@common.at_install(False)
@common.post_install(True)
class TestAllowedFileType(common.SavepointCase):
    """
    Check that only the admin user can manage allowed file types and that downloads are blocked
    for non-admin users when trying to download files with a file type that is not allowed
    """

    @classmethod
    def setUpClass(cls):
        """
        Create allowed file type and attachments for blocked/unblocked files
        """
        super(TestAllowedFileType, cls).setUpClass()

        cls.AllowedFileType = cls.env["udes.allowed_file_type"]

        cls.allowed_file_type_csv = cls.env.ref("udes_security.udes_allowed_file_type_csv")
        cls.allowed_file_type_rtf = cls.env.ref("udes_security.udes_allowed_file_type_rtf")
        cls.allowed_file_type_txt = cls.env.ref("udes_security.udes_allowed_file_type_txt")
        cls.allowed_file_type_json = cls.env.ref("udes_security.udes_allowed_file_type_json")

        # Set TXT and JSON allowed file types to inactive, so they are blocked for the tests
        cls.allowed_file_type_txt.active = False
        cls.allowed_file_type_json.active = False

        cls.atch_txt_file = cls.create_attachment("text_file.txt")
        cls.atch_csv_file = cls.create_attachment("spreadsheet_file.csv")
        cls.atch_rtf_file = cls.create_attachment("rtf_file.rtf")
        cls.atch_html_file = cls.create_attachment("web_page.html")

    @classmethod
    def _get_file_path(self, filename):
        """Get file path from supplied filename"""
        module_file = sys.modules[self.__module__].__file__
        module = get_resource_from_path(module_file)[0]
        files_path_str = get_resource_path(module, "tests", "files")
        files_path = pathlib.Path(files_path_str)
        file_path = files_path.joinpath(filename)

        return file_path

    @classmethod
    def create_attachment(self, filename):
        """Create attachment from supplied filename"""
        IrAttachment = self.env["ir.attachment"]

        file_path = self._get_file_path(filename)

        attachment = IrAttachment.create(
            {
                "name": file_path.name,
                "datas_fname": file_path.name,
                "datas": base64.b64encode(file_path.read_bytes()),
            }
        )
        return attachment

    @classmethod
    def update_attachment(self, attachment, filename):
        """Update attachment data from supplied filename"""
        file_path = self._get_file_path(filename)

        res = attachment.write(
            {
                "name": file_path.name,
                "datas_fname": file_path.name,
                "datas": base64.b64encode(file_path.read_bytes()),
            }
        )

        return res

    @classmethod
    def create_allowed_file_type(self, file_type, **kwargs):
        """Create allowed file type record from supplied file type"""
        allowed_file_type_vals = {"name": file_type}
        allowed_file_type_vals.update(kwargs)

        allowed_file_type = self.AllowedFileType.create(allowed_file_type_vals)

        return allowed_file_type

    def test_sets_allowed_attachment_active(self):
        """
        Assert that an attachment with an allowed file type is set to active.

        Also assert that the attachment is set to active on either of the following conditions:
            1. The relevant inactive allowed file type record is set to active
            2. A new allowed file type record is created for the attachment's file type
        """
        self.assertTrue(self.atch_csv_file.active)
        self.assertTrue(self.atch_rtf_file.active)

        # Set TXT allowed file type to active, unblocking TXT files
        self.allowed_file_type_txt.active = True
        self.assertTrue(self.atch_txt_file.active)

        # Create HTML allowed file type record, unblocking HTML files
        self.create_allowed_file_type(("html"))
        self.assertTrue(self.atch_html_file.active)

    def test_sets_blocked_attachment_inactive(self):
        """
        Assert that an attachment with a blocked file type is set to active.

        Also assert that the attachment is set to inactive on either of the following conditions:
            1. The relevant allowed file type record is set to inactive
            2. The relevant allowed file type record is deleted
        """
        self.assertFalse(self.atch_txt_file.active)
        self.assertFalse(self.atch_html_file.active)

        # Set CSV allowed file type to inactive, blocking CSV files
        self.allowed_file_type_csv.active = False
        self.assertFalse(self.atch_csv_file.active)

        # Delete RTF allowed file type record, blocking RTF files
        self.allowed_file_type_rtf.unlink()
        self.assertFalse(self.atch_rtf_file.active)

    def test_allowed_file_type_unique(self):
        """Assert that only one blocked file type record can exist for each file type"""
        # Create another allowed file type for csv and assert that an Integrity Error is raised
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.create_allowed_file_type(self.allowed_file_type_csv.name)

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
        Assert that the file type is properly set on attachment and is updated when the file changes
        """
        self.assertEqual(self.atch_csv_file.datas_file_type, "csv")

        # Replace csv file on csv attachment with a json file and check file type is updated
        self.update_attachment(self.atch_csv_file, "json_file.json")
        self.assertEqual(self.atch_csv_file.datas_file_type, "json")
