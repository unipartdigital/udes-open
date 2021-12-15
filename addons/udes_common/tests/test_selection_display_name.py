"""Tests for selection field display name"""

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


@tagged("post_install")
class TestSelectionDisplayName(common.SavepointCase):
    """Tests for selection_display_name()"""

    @classmethod
    def setUpClass(cls):
        """
        Pull in recordsets defined in `base` modules data, to allow us to test
        without needing to mock selection fields everywhere

        NB: No related selection fields exist in `base` i.e
        my_field = fields.Selection(related="state")
        and it is not possible to mock fields in tests (as far as i am aware)
        so there is no unittest for this scenario, however it has been manually tested
        """
        super(TestSelectionDisplayName, cls).setUpClass()

        ResPartnerBank = cls.env["res.partner.bank"]
        IrFilters = cls.env["ir.filters"]

        # A random recordset on a model with a normal selection field
        cls.model_overview_report = cls.env.ref("base.report_ir_model_overview")
        # A random recordset on a model with a generated selection field (function)
        cls.main_partner = cls.env.ref("base.main_partner")
        # There are no recordsets on res.partner.bank, but it has a lambda generated
        # selection field, so we just create one
        cls.res_partner_bank_recordset = ResPartnerBank.create(
            dict(
                acc_number="60-16-13 31926819",
                partner_id=cls.main_partner.id,
            )
        )
        # There are no recordsets on ir.filters, but it has a generated
        # selection field (by string name of function), so we just create one
        cls.ir_filters_recordset = IrFilters.create(
            dict(
                name="TestABC",
                user_id=cls.env.user.id,
                model_id="res.groups",
            )
        )

    def test_basic_selection_field(self):
        """Check function gives the expected value from a normal selection field"""
        normal_output = self.model_overview_report.report_type
        self.assertEqual(normal_output, "qweb-pdf")

        alt_output = self.model_overview_report.selection_display_name("report_type")
        self.assertEqual(alt_output, "PDF")

    def test_generated_selection_field(self):
        """Check function gives the expected value from a selection field
        which uses a function to determine its selection values
        (where the function is defined in the field as a callable that lives outside the class)
        """
        normal_output = self.main_partner.lang
        self.assertEqual(normal_output, "en_US")

        alt_output = self.main_partner.selection_display_name("lang")
        self.assertEqual(alt_output, "English (US)")

    def test_generated_selection_field2(self):
        """Check function gives the expected value from a selection field
        which uses a function to determine its selection values
        (where the function is defined in the field as a string)
        """
        normal_output = self.ir_filters_recordset.model_id
        self.assertEqual(normal_output, "res.groups")

        alt_output = self.ir_filters_recordset.selection_display_name("model_id")
        self.assertEqual(alt_output, "Access Groups")

    def test_generated_lambda_selection_field(self):
        """Check function gives the expected value from a selection field
        which uses a lambda function to determine its selection values
        """
        normal_output = self.res_partner_bank_recordset.acc_type
        self.assertEqual(normal_output, "bank")

        alt_output = self.res_partner_bank_recordset.selection_display_name("acc_type")
        self.assertEqual(alt_output, "Normal")

    def test_fetching_nonexistent_field(self):
        """Ensure function fails with appropriate warning message if developer
        attempts to get a selection field which does not exist on the model
        in place of a KeyError
        """
        with self.assertRaises(ValidationError):
            self.res_partner_bank_recordset.selection_display_name("state")

    def test_fetching_unset_selection_field(self):
        """Ensure function returns False if the selection field on the recordset is not set"""
        self.model_overview_report.report_type = False

        normal_output = self.model_overview_report.report_type
        self.assertEqual(normal_output, False)

        alt_output = self.model_overview_report.selection_display_name("report_type")
        self.assertEqual(alt_output, False)
