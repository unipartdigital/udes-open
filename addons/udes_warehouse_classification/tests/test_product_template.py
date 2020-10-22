from .common import Base


class TestWarehouseClassificationPicking(Base):
    """
        # For a given product find the classification messages for specified report,
        # 1. report a on it's own - banana
        # 2. not matching report type - banana
        # 3. report a and b - honeydew
        # 4. report a and report a on inbound (i.e. 2 messages for a report) - cherry
        # 5. get report messages from 2 products - banana+honeydew
        # 6. no classifications - apple
    """

    def test01_basic_report(self):
        messages = self.banana.get_classification_messages_for_report(
            self.report_a.report_name
        )
        test_messages = ["Inbound, Report a, Report"]
        self.assertEqual(messages, test_messages)

    def test02_report_not_for_product(self):
        self.assertFalse(
            self.banana.get_classification_messages_for_report(
                self.report_b.report_name
            )
        )

    def test03_multiple_reports(self):
        messages_1 = self.honeydew.get_classification_messages_for_report(
            self.report_a.report_name
        )
        messages_2 = self.honeydew.get_classification_messages_for_report(
            self.report_b.report_name
        )
        test_messages = ["Report a Report", "Report b Report"]
        self.assertIn(messages_1[0], test_messages)
        self.assertIn(messages_2[0], test_messages)

    def test04_two_messages_one_product(self):
        messages = self.cherry.get_classification_messages_for_report(
            self.report_a.report_name
        )
        test_messages = ["Report a Report", "Inbound, Report a, Report"]
        self.assertCountEqual(messages, test_messages)

    def test05_messages_from_two_products(self):
        products = self.banana + self.honeydew
        messages = products.get_classification_messages_for_report(
            self.report_a.report_name
        )
        test_messages = ['Inbound, Report a, Report', 'Report a Report']
        self.assertCountEqual(messages, test_messages)

    def test06_no_classfications_for_product(self):
        with self.assertLogs(
            "odoo.addons.udes_warehouse_classification.models.product_template"
        ) as cm:
            messages = self.apple.get_classification_messages_for_report(
                self.report_b.report_name
            )
        self.assertFalse(messages)
        self.assertIn("Product Test product Apple has no warehouse classifications.", cm.output[0])
