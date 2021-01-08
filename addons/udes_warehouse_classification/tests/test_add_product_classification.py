"""Tests for the Add Product Classification wizard."""

import base64
import re

from odoo.exceptions import ValidationError

from . import common


class AddProductClassificationTestCase(common.Base):
    """Unit tests for the Add Product Classification wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Classification = cls.env["product.warehouse.classification"]

        classifications = Classification.browse()
        classifications |= cls.create_classification("A")
        classifications |= cls.create_classification("B")
        cls.classifications = classifications

        cls.active_ids = classifications.mapped("id")

        cls.lemon = cls.create_product("Lemon")
        cls.lime = cls.create_product("Lime")

    def _create_upload(self, names):
        data = "\n".join([re.sub(r"(?=[A-Z])", "product", n, count=1) for n in names])
        return base64.b64encode(data.encode("utf-8"))

    def test_adds_classifications(self):
        """Verify that uploaded products are classified."""
        AddProductClassification = self.env[
            "udes_warehouse_classification.add_product_classification"
        ]

        upload = self._create_upload(["Lemon", "Lime"])
        wizard = AddProductClassification.create({"file_data": upload})

        self.assertFalse(self.lemon.u_product_warehouse_classification_ids)
        self.assertFalse(self.lime.u_product_warehouse_classification_ids)

        wizard.with_context(active_ids=self.active_ids).upload_products()

        self.assertEqual(self.lemon.u_product_warehouse_classification_ids, self.classifications)
        self.assertEqual(self.lime.u_product_warehouse_classification_ids, self.classifications)

    def test_handles_leading_and_trailing_whitespace_in_upload_file(self):
        """Check that leading and trailing whitespace does not prevent upload."""
        AddProductClassification = self.env[
            "udes_warehouse_classification.add_product_classification"
        ]

        upload = self._create_upload(["  \u200b \t\r Lemon \t \u00a0 ", " \u00a0 Lime  \u200b "])
        wizard = AddProductClassification.create({"file_data": upload})

        self.assertFalse(self.lemon.u_product_warehouse_classification_ids)
        self.assertFalse(self.lime.u_product_warehouse_classification_ids)

        wizard.with_context(active_ids=self.active_ids).upload_products()

        self.assertEqual(self.lemon.u_product_warehouse_classification_ids, self.classifications)
        self.assertEqual(self.lime.u_product_warehouse_classification_ids, self.classifications)

    def test_rejects_input_with_invalid_default_codes(self):
        AddProductClassification = self.env[
            "udes_warehouse_classification.add_product_classification"
        ]

        upload = self._create_upload(["Lemon", "Lime", "Mango"])
        wizard = AddProductClassification.create({"file_data": upload})

        self.assertFalse(self.lemon.u_product_warehouse_classification_ids)
        self.assertFalse(self.lime.u_product_warehouse_classification_ids)

        with self.assertRaises(ValidationError) as cm:
            wizard.with_context(active_ids=self.active_ids).upload_products()

        self.assertEqual(cm.exception.args[0], "Unknown product code(s) 'productMango'")
        self.assertFalse(self.lemon.u_product_warehouse_classification_ids)
        self.assertFalse(self.lime.u_product_warehouse_classification_ids)
