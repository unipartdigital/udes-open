"""Unit tests for the ProductTemplate model."""

from odoo.exceptions import ValidationError

from . import common


class ProductTemplateDeletionTestCase(common.BaseUDES):
    """Tests for prevention of deletion of product templates."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.apple_template = cls.apple.product_tmpl_id
        cls.red_apple = cls.apple

    def test_raises_error_on_deletion(self):
        """Unlinking a product template should raise an error."""
        expected_message = "Products may not be deleted. Please archive them instead."

        with self.assertRaisesRegex(ValidationError, expected_message):
            self.apple_template.unlink()

        self.assertTrue(self.apple_template.exists())
        self.assertEqual(self.apple_template.product_variant_ids, self.red_apple)
