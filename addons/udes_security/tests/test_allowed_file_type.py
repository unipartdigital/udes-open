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
class TestBlockedFileType(common.SavepointCase):
    """
    Check that only the admin user can manage blocked file types and that downloads are blocked
    for non-admin users when trying to download files with a blocked file type
    """

    @classmethod
    def setUpClass(cls):
        """
        Create blocked file type and attachments for blocked/unblocked files
        """
        super(TestBlockedFileType, cls).setUpClass()

        cls.BlockedFileType = cls.env["udes.blocked_file_type"]

        cls.atch_txt_file = cls.create_attachment("text_file.txt")
        cls.atch_csv_file = cls.create_attachment("spreadsheet_file.csv")

        cls.blocked_file_type_txt = cls.create_blocked_file_type("txt")

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

        res = attachment.write({
            "name": file_path.name,
            "datas_fname": file_path.name,
            "datas": base64.b64encode(file_path.read_bytes()),
        })

        return res

    @classmethod
    def create_blocked_file_type(self, file_type, **kwargs):
        """Create blocked file type from supplied file type"""
        blocked_file_type_vals = {"name": file_type}
        blocked_file_type_vals.update(kwargs)

        blocked_file_type = self.BlockedFileType.create(blocked_file_type_vals)

        return blocked_file_type

    def test_blocked_file_active_status(self):
        """Test that attachment is inactive if it's file type is blocked or otherwise active"""
        # Check txt file is inactive and csv file is active
        self.assertFalse(self.atch_txt_file.active)
        self.assertTrue(self.atch_csv_file.active)

        # Set txt blocked file type to inactive and check txt attachment is now active
        self.blocked_file_type_txt.active = False
        self.assertTrue(self.atch_txt_file.active)

        # Check that csv file is unaffected and still active
        self.assertTrue(self.atch_csv_file.active)

    def test_blocked_file_type_deleted(self):
        """Test that deleting an active blocked file type sets blocked attachments to active"""
        # Check txt file is active after txt blocked file type record is deleted
        self.blocked_file_type_txt.unlink()
        self.assertTrue(self.atch_txt_file.active)

    def test_blocked_file_type_unique(self):
        """Test that only one blocked file type record can exist for each file type"""
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.create_blocked_file_type("txt")

    def test_blocked_file_type_change_file_type_prevented(self):
        """Test that the file type on a blocked file type record cannot be changed"""
        with self.assertRaises(UserError):
            self.blocked_file_type_txt.name = "other_txt"

    def test_blocked_file_type_format_name(self):
        """Test that file type name is properly formatted"""
        json_file_type = "json"
        json_unformatted_file_types = ("JSON", ".json", ".JSON")

        # Ensure that _format_name properly formats each unformatted file type
        [
            self.assertEquals(self.BlockedFileType._format_name(file_type), json_file_type)
            for file_type in json_unformatted_file_types
        ]

    def test_attachment_file_type(self):
        """Test that the file type is properly set on attachment"""
        self.assertEquals(self.atch_csv_file.datas_file_type, "csv")

        # Replace csv file on csv attachment with a json file and check file type is updated
        self.update_attachment(self.atch_csv_file, "json_file.json")
        self.assertEquals(self.atch_csv_file.datas_file_type, "json")
