# -*- coding: utf-8 -*-

from . import common


class TestProductActiveSync(common.BaseUDES):
    """Tests for syncing the active state of products to templates"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.apple_template = cls.apple.product_tmpl_id
        cls.red_apple = cls.apple
        cls.green_apple = cls.red_apple.copy({"product_tmpl_id": cls.apple_template.id})

    def test01_template_deactivated_when_all_variants_inactive(self):
        """Tests that product templates are deactivated when all of their variants are inactive"""
        self.red_apple.active = False
        self.green_apple.active = False

        self.assertTrue(self.apple_template.active)
        (self.red_apple | self.green_apple).sync_active_to_templates()
        self.assertFalse(self.apple_template.active)

    def test02_template_activated_when_any_variants_active(self):
        """Tests that product templates are activated when any of their variants are active"""
        self.apple_template.active = False
        self.red_apple.active = False
        self.green_apple.active = True

        self.assertFalse(self.apple_template.active)
        (self.red_apple | self.green_apple).sync_active_to_templates()
        self.assertTrue(self.apple_template.active)

    def test03_template_remains_active_when_any_variants_are_active(self):
        """Tests that product templates remain active when any of their variants are active"""
        self.red_apple.active = False
        self.green_apple.active = True

        self.assertTrue(self.apple_template.active)
        self.red_apple.sync_active_to_templates()
        self.assertTrue(self.apple_template.active)