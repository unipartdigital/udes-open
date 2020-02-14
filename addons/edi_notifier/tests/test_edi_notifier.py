from unittest.mock import patch
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.addons.edi.tests.common import EdiCase
from odoo.tools import mute_logger


class EdiNotifierCase(EdiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiDocumentType = cls.env["edi.document.type"]
        EdiDocument = cls.env["edi.document"]
        IrModel = cls.env["ir.model"]

        # Create document type
        cls.doc_type = EdiDocumentType.create(
            {
                "name": "Test EDI document",
                "model_id": IrModel._get_id("edi.document.model"),
            }
        )

        # Create document
        cls.doc = EdiDocument.create(
            {"name": "ToDo list", "doc_type_id": cls.doc_type.id, "state": "draft",}
        )

    def mock_send_mail(self):
        return patch.object(
            self.env["mail.template"].__class__, "send_mail", autospec=True
        )

    def create_transfer(self, doc):
        IrModel = self.env["ir.model"]
        EdiGateway = self.env["edi.gateway"]
        EdiTransfer = self.env["edi.transfer"]

        self.gateway = EdiGateway.create(
            {
                "name": "Test gateway",
                "model_id": IrModel._get_id("edi.connection.model"),
            }
        )
        # Create transfers
        self.transfer = EdiTransfer.create({"gateway_id": self.gateway.id,})
        self.transfer.doc_ids += doc

    def setup_cron(self, nextcall_time):
        IrCron = self.env["ir.cron"]
        action = self.notifier.action_view_cron()
        self.cron = IrCron.with_context(action["context"]).create(
            {"name": "Test cron job", "nextcall": self._convert_time(nextcall_time),}
        )

    def _convert_time(self, time):
        return fields.Datetime.to_string(time)

    def make_note(self, res, text):
        self.env["mail.message"].create(
            {"model": res._name, "res_id": res.id, "body": text,}
        )


class TestNotifier(EdiNotifierCase):
    """EDI generic notifier tests"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiNotifier = cls.env["edi.notifier"]
        IrModel = cls.env["ir.model"]

        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc success",
                "model_id": IrModel._get_id("edi.notifier.model"),
                "doc_type_ids": [(6, False, cls.doc_type.ids)],
                "active": True,
            }
        )

    def test_not_active_if_no_doc_types(self):
        self.notifier.doc_type_ids = [(5, False, False)]
        self.assertFalse(self.notifier.active)

    def test_throw_error_if_setting_active_if_no_doc_types(self):
        self.notifier.doc_type_ids = [(5, False, False)]
        with self.assertRaises(ValidationError):
            self.notifier.active = True

    def test_action_veiw_cron(self):
        IrCron = self.env["ir.cron"]
        action = self.notifier.action_view_cron()
        self.assertEqual(len(IrCron.search(action["domain"])), 0)
        cron = IrCron.with_context(action["context"]).create({"name": "Test cron job",})
        self.assertIn(cron, self.notifier.cron_ids)
        self.assertEqual(self.notifier.cron_count, 1)
        action = self.notifier.action_view_cron()
        self.assertEqual(len(IrCron.search(action["domain"])), 1)


class TestSuccess(EdiNotifierCase):
    """EDI success notifier tests"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiNotifier = cls.env["edi.notifier"]
        IrModel = cls.env["ir.model"]

        cls.email_template = cls.env.ref(
            "edi_notifier.email_template_edi_document_success"
        )
        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc success",
                "model_id": IrModel._get_id("edi.notifier.email.success"),
                "doc_type_ids": [(6, False, cls.doc_type.ids)],
                "template_id": cls.email_template.id,
                "active": True,
            }
        )

    def test_send_mail_on_success(self):
        with self.mock_send_mail() as send_mail_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mail_mock.assert_called_once()
        send_mail_mock.assert_called_with(
            self.email_template, self.doc.id, force_send=True
        )

    def test_dont_send_if_not_active(self):
        self.notifier.active = False
        with self.mock_send_mail() as send_mail_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mail_mock.assert_not_called()

    def test_dont_send_on_failure(self):
        self.doc.doc_type_id = self.doc_type_unknown
        self.notifier.doc_type_ids = [(6, False, self.doc_type_unknown.ids)]
        with mute_logger(
            "odoo.addons.edi.models.edi_issues"
        ), self.mock_send_mail() as send_mail_mock:
            self.doc.action_execute()
        send_mail_mock.assert_not_called()


class TestFailed(EdiNotifierCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiNotifier = cls.env["edi.notifier"]
        IrModel = cls.env["ir.model"]

        cls.email_template = cls.env.ref(
            "edi_notifier.email_template_edi_document_failed"
        )
        cls.doc.doc_type_id = cls.doc_type_unknown
        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc failed",
                "model_id": IrModel._get_id("edi.notifier.email.failed"),
                "doc_type_ids": [(6, False, cls.doc_type_unknown.ids)],
                "template_id": cls.email_template.id,
                "active": True,
            }
        )

    def test_send_on_failure(self):
        with mute_logger(
            "odoo.addons.edi.models.edi_issues"
        ), self.mock_send_mail() as send_mail_mock:
            self.doc.action_execute()
        self.assertNotEqual(self.doc.state, "done")
        send_mail_mock.assert_called_with(
            self.email_template, self.doc.id, force_send=True
        )

    def test_dont_send_on_success(self):
        self.doc.doc_type_id = self.doc_type
        self.notifier.doc_type_ids = [(6, False, self.doc_type.ids)]
        with self.mock_send_mail() as send_mail_mock:
            self.doc.action_execute()
        send_mail_mock.assert_not_called()


class TestMissing(EdiNotifierCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiNotifier = cls.env["edi.notifier"]
        IrModel = cls.env["ir.model"]
        cls.doc_type_raw = cls.env.ref("edi.raw_document_type")
        cls.email_template = cls.env.ref(
            "edi_notifier.email_template_edi_document_not_received"
        )

        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc missing",
                "model_id": IrModel._get_id("edi.notifier.email.missing"),
                "doc_type_ids": [(6, False, cls.doc_type.ids)],
                "template_id": cls.email_template.id,
                "active": True,
            }
        )

    def test_cron_trigger_missing_not_reported(self):
        self.setup_cron(datetime.now() - timedelta(hours=1))
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_called_once()
        send_mail_mock.assert_called_with(
            self.email_template, self.doc_type.id, force_send=True
        )

    def test_cron_trigger_missing_already_reported(self):
        dtime = datetime.now() - timedelta(hours=1)
        self.doc_type.x_last_checked_not_received = self._convert_time(dtime)
        self.setup_cron(dtime)
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_not_called()

    def test_cron_trigger_recived(self):
        raw_doc = self.create_document(self.doc_type_raw)
        self.create_transfer(raw_doc)
        self.create_input_attachment(raw_doc, "res.users.csv")
        self.notifier.doc_type_ids = [(6, False, self.doc_type_raw.ids)]
        self.setup_cron(datetime.now())
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_not_called()


class TestMissingInRange(EdiNotifierCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiNotifier = cls.env["edi.notifier"]
        IrModel = cls.env["ir.model"]
        cls.doc_type_raw = cls.env.ref("edi.raw_document_type")
        cls.email_template = cls.env.ref(
            "edi_notifier.email_template_edi_document_not_received"
        )
        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc missing",
                "model_id": IrModel._get_id("edi.notifier.email.missing.in.range"),
                "doc_type_ids": [(6, False, cls.doc_type.ids)],
                "template_id": cls.email_template.id,
                "lookback_hours": 3,
                "active": True,
            }
        )

    def test_dont_send_if_recived(self):
        raw_doc = self.create_document(self.doc_type_raw)
        self.create_transfer(raw_doc)
        self.create_input_attachment(raw_doc, "res.users.csv")
        self.notifier.doc_type_ids = [(6, False, self.doc_type_raw.ids)]
        self.setup_cron(datetime.now())
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_not_called()

    def test_send_if_recived_out_of_timeframe(self):
        raw_doc = self.create_document(self.doc_type_raw)
        self.create_transfer(raw_doc)
        self.create_input_attachment(raw_doc, "res.users.csv")
        self.notifier.doc_type_ids = [(6, False, self.doc_type_raw.ids)]
        self.setup_cron(datetime.now() + timedelta(hours=4))
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_called_with(
            self.email_template, self.doc_type_raw.id, force_send=True
        )

    def test_dont_send_if_recived_within_timeframe(self):
        raw_doc = self.create_document(self.doc_type_raw)
        self.create_transfer(raw_doc)
        self.create_input_attachment(raw_doc, "res.users.csv")
        self.notifier.doc_type_ids = [(6, False, self.doc_type_raw.ids)]
        self.setup_cron(datetime.now() + timedelta(hours=1))
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_not_called()
