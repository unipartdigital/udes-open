from odoo.addons.edi_sale.tests.common import EdiSaleCase

from mock import patch

class TestSaleNotifier(EdiSaleCase):
    """EDI sale order request tests"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc_type_tutorial = cls.env.ref(
            'edi_sale.sale_request_tutorial_document_type'
        )

    @classmethod
    def create_tutorial(cls, *filenames, fail_fast=True):
        """Create sale order request tutorial document"""
        cls.doc_type_tutorial.fail_fast = fail_fast
        return cls.create_input_document(cls.doc_type_tutorial, *filenames)

    def mock_invalid_partner_updates(self):
        """Patch function that checks partners to allow fail_fast=False to be used"""
        return patch.object(
            self.env["edi.sale.request.document"].__class__,
            "remove_sales_for_invalid_partner_updates",
            autospec=True
        )

    def test_suffix_no_errors(self):
        """Test that no warning suffix is generated when there are no errors"""
        doc = self.create_tutorial('order01.csv', fail_fast=False)
        with self.mock_invalid_partner_updates():
            self.assertTrue(doc.action_execute())
        self.assertFalse(doc.notifier_subject_suffix)

    def test_suffix_invalid_orderline(self):
        """Test that a suffix is generated when an orderline has an error"""
        doc = self.create_tutorial('order02.csv', fail_fast=False)
        with self.mock_invalid_partner_updates():
            self.assertTrue(doc.action_execute())
        self.assertTrue(doc.notifier_subject_suffix)

    def test_suffix_invalid_partner(self):
        """Test that a suffix is generated when a partner has an error"""
        doc = self.create_tutorial('order01.csv', fail_fast=False)
        self.assertTrue(doc.action_prepare())
        doc.partner_ids[0].error = True
        with self.mock_invalid_partner_updates():
            self.assertTrue(doc.action_execute())
        self.assertTrue(doc.notifier_subject_suffix)
