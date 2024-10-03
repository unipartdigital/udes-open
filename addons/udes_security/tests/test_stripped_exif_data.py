import base64
import pathlib
import sys
import io
from PIL import Image
from odoo.tests import common
from odoo.modules.module import get_resource_from_path, get_resource_path


class TestStrippedExifData(common.SavepointCase):
    @classmethod
    def setUpClass(cls):
        super(TestStrippedExifData, cls).setUpClass()
        cls.IrAttachment = cls.env["ir.attachment"]

    @classmethod
    def _get_file_path(cls, filename):
        module_file = sys.modules[cls.__module__].__file__
        module = get_resource_from_path(module_file)[0]
        files_path_str = get_resource_path(module, "tests", "files")
        files_path = pathlib.Path(files_path_str)
        file_path = files_path.joinpath(filename)

        return file_path

    @classmethod
    def get_attachment_datas(cls, filename):
        file_path = cls._get_file_path(filename)

        attachment = base64.b64encode(file_path.read_bytes())

        return attachment

    def test_remove_exif_data(self):
        attachment_datas = self.get_attachment_datas("image_with_exif_data.jpg")

        original_data = base64.b64decode(attachment_datas)
        original_image = Image.open(io.BytesIO(original_data))
        self.assertIsNotNone(original_image._getexif())
        # On attachment create automatically removes the exif data
        attachment = self.IrAttachment.create({
            "name": "image_with_exif_data.jpg",
            "datas": attachment_datas,
        })

        processed_image = Image.open(io.BytesIO(base64.b64decode(attachment.datas)))

        self.assertIsNone(processed_image._getexif())
