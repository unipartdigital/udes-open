from unittest.mock import patch
from unittest import mock
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import ValidationError, UserError
from odoo.addons.edi.tests.common import EdiCase
from odoo.tools import config, mute_logger


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
            {
                "name": "ToDo list",
                "doc_type_id": cls.doc_type.id,
                "state": "draft",
            }
        )

        # Set common safety config and enable for tests
        cls.safety = "edi.enable_edi_notifications"
        config.misc["edi"] = {"enable_edi_notifications": 1}

    def mute_issues(self):
        return mute_logger("odoo.addons.edi.models.edi_issues")

    def mock_send_mail(self):
        return patch.object(self.env["mail.template"].__class__, "send_mail", autospec=True)

    def mock_send(self):
        return patch.object(self.env["mail.mail"].__class__, "send", autospec=True)

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
        self.transfer = EdiTransfer.create(
            {
                "gateway_id": self.gateway.id,
            }
        )
        self.transfer.doc_ids += doc

    def setup_cron(self, nextcall_time):
        IrCron = self.env["ir.cron"]
        action = self.notifier.action_view_cron()
        self.cron = IrCron.with_context(action["context"]).create(
            {
                "name": "Test cron job",
                "nextcall": self._convert_time(nextcall_time),
            }
        )

    def _convert_time(self, time):
        return fields.Datetime.to_string(time)

    def make_note(self, res, text):
        self.env["mail.message"].create(
            {
                "model": res._name,
                "res_id": res.id,
                "body": text,
            }
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
                "safety": cls.safety,
            }
        )

    def test_not_active_if_no_doc_types(self):
        self.notifier.doc_type_ids = [(5, False, False)]
        self.assertFalse(self.notifier.active)

    def test_throw_error_if_setting_active_if_no_doc_types(self):
        self.notifier.doc_type_ids = [(5, False, False)]
        with self.assertRaises(UserError):
            self.notifier.active = True

    def test_action_veiw_cron(self):
        IrCron = self.env["ir.cron"]
        action = self.notifier.action_view_cron()
        self.assertEqual(len(IrCron.search(action["domain"])), 0)
        cron = IrCron.with_context(action["context"]).create(
            {
                "name": "Test cron job",
            }
        )
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

        cls.email_template = cls.env.ref("edi_notifier.email_template_edi_document_success")
        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc success",
                "model_id": IrModel._get_id("edi.notifier.email.success"),
                "doc_type_ids": [(6, False, cls.doc_type.ids)],
                "template_id": cls.email_template.id,
                "active": True,
                "safety": cls.safety,
            }
        )

    def test_send_mail_on_success(self):
        with self.mock_send_mail() as send_mail_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mail_mock.assert_called_once()
        send_mail_mock.assert_called_with(
            self.email_template, self.doc.id, force_send=True, email_values=None
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
        with self.mute_issues(), self.mock_send_mail() as send_mail_mock:
            self.doc.action_execute()
        send_mail_mock.assert_not_called()

    def test_send_notes_on_success(self):
        self.notifier.include_notes = True
        note_text = "Note for testing!"
        self.make_note(self.doc, note_text)
        with self.mock_send() as send_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertIn(note_text, message.body_html)

    def test_dont_send_notes_on_success(self):
        self.notifier.include_notes = False
        note_text = "Note for testing!"
        self.make_note(self.doc, note_text)
        with self.mock_send() as send_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertNotIn(note_text, message.body_html)

    def test_sends_output_attachment_on_success(self):
        self.notifier.include_attachments = "output"
        attachment = self.create_output_attachment(self.doc, "out.csv")
        with self.mock_send() as send_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertEqual(message.attachment_ids, attachment)

    def test_sends_input_attachment_on_success(self):
        self.notifier.include_attachments = "input"
        attachment = self.create_input_attachment(self.doc, "in.csv")
        with self.mock_send() as send_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertEqual(message.attachment_ids, attachment)

    def test_sends_all_attachments_on_success(self):
        Attachment = self.env["ir.attachment"]
        self.notifier.include_attachments = "all"
        attachments = Attachment.browse()
        attachments |= self.create_input_attachment(self.doc, "in.csv")
        attachments |= self.create_output_attachment(self.doc, "out.csv")
        with self.mock_send() as send_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertEqual(message.attachment_ids, attachments)

    def test_sends_no_attachment_on_success(self):
        self.notifier.include_attachments = "none"
        self.create_input_attachment(self.doc, "in.csv")
        self.create_output_attachment(self.doc, "out.csv")
        with self.mock_send() as send_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertFalse(message.attachment_ids)

    def test_suffix_included_in_subject(self):
        """Assert that the suffix is included in the subject if specified."""
        self.doc.notifier_subject_suffix = " TEST_STRING"
        with self.mock_send() as send_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertEqual(
            self.doc.notifier_subject_suffix,
            message.subject[-len(self.doc.notifier_subject_suffix) :],
        )


class TestFailed(EdiNotifierCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiNotifier = cls.env["edi.notifier"]
        IrModel = cls.env["ir.model"]

        cls.email_template = cls.env.ref("edi_notifier.email_template_edi_document_failed")
        cls.doc.doc_type_id = cls.doc_type_unknown
        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc failed",
                "model_id": IrModel._get_id("edi.notifier.email.failed"),
                "doc_type_ids": [(6, False, cls.doc_type_unknown.ids)],
                "template_id": cls.email_template.id,
                "active": True,
                "safety": cls.safety,
            }
        )

    def rig_execute_to_fail(self, doc):
        return patch.object(
            doc.__class__,
            "execute_records",
            autospec=True,
            side_effect=ValidationError,
        )

    def test_send_on_prepare_failure(self):
        with self.mute_issues(), self.mock_send_mail() as send_mail_mock:
            self.doc.action_prepare()
        self.assertEqual(self.doc.state, "draft")
        send_mail_mock.assert_called_once()
        send_mail_mock.assert_called_with(
            self.email_template, self.doc.id, force_send=True, email_values=None
        )

    def test_send_on_prepare_failure_within_execute(self):
        with self.mute_issues(), self.mock_send_mail() as send_mail_mock:
            self.doc.action_execute()
        self.assertEqual(self.doc.state, "draft")
        send_mail_mock.assert_called_once()
        send_mail_mock.assert_called_with(
            self.email_template, self.doc.id, force_send=True, email_values=None
        )

    def test_send_on_execute_failure(self):
        self.doc.doc_type_id = self.doc_type
        self.notifier.write({"doc_type_ids": [(6, False, self.doc_type.ids)]})

        with self.mute_issues(), self.mock_send_mail() as send_mail_mock, self.rig_execute_to_fail(
            self.doc
        ):
            self.doc.action_execute()
        self.assertEqual(self.doc.state, "prep")
        send_mail_mock.assert_called_once()
        send_mail_mock.assert_called_with(
            self.email_template, self.doc.id, force_send=True, email_values=None
        )

    def test_dont_send_on_success(self):
        self.doc.doc_type_id = self.doc_type
        self.notifier.doc_type_ids = [(6, False, self.doc_type.ids)]
        with self.mock_send_mail() as send_mail_mock:
            self.doc.action_execute()
        send_mail_mock.assert_not_called()

    def test_send_issues_on_failure(self):
        self.notifier.include_issues = True
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")

        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertIn("Unknown document type", message.body_html)

    def test_dont_send_issues_on_failure(self):
        self.notifier.include_issues = False
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertNotIn("Unknown document type", message.body_html)

    def test_send_notes_on_failure(self):
        self.notifier.include_notes = True
        note_text = "Note for testing!"
        self.make_note(self.doc, note_text)
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertIn(note_text, message.body_html)

    def test_dont_send_notes_on_failure(self):
        self.notifier.include_notes = False
        note_text = "Note for testing!"
        self.make_note(self.doc, note_text)
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertNotIn(note_text, message.body_html)

    def test_send_notes_and_issues_on_failure(self):
        self.notifier.write(
            {
                "include_notes": True,
                "include_issues": True,
            }
        )
        note_text = "Note for testing!"
        self.make_note(self.doc, note_text)
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertIn(note_text, message.body_html)
        self.assertIn("Unknown document type", message.body_html)

    def test_sends_output_attachment_on_failure(self):
        self.notifier.include_attachments = "output"
        attachment = self.create_output_attachment(self.doc, "out.csv")
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertEqual(message.attachment_ids, attachment)

    def test_sends_input_attachment_on_failure(self):
        self.notifier.include_attachments = "input"
        attachment = self.create_input_attachment(self.doc, "in.csv")
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertEqual(message.attachment_ids, attachment)

    def test_sends_all_attachments_on_failure(self):
        Attachment = self.env["ir.attachment"]
        self.notifier.include_attachments = "all"
        attachments = Attachment.browse()
        attachments |= self.create_input_attachment(self.doc, "in.csv")
        attachments |= self.create_output_attachment(self.doc, "out.csv")
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertEqual(message.attachment_ids, attachments)

    def test_sends_no_attachment_on_failure(self):
        self.notifier.include_attachments = "none"
        self.create_input_attachment(self.doc, "in.csv")
        self.create_output_attachment(self.doc, "out.csv")
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertFalse(message.attachment_ids)

    def test_suffix_included_in_subject(self):
        """Assert that the suffix is included in the subject if specified."""
        self.doc.notifier_subject_suffix = " TEST_STRING"
        with self.mute_issues(), self.mock_send() as send_mock:
            self.assertFalse(self.doc.action_execute())
        self.assertEqual(self.doc.state, "draft")
        send_mock.assert_called_once()
        message = send_mock.call_args[0][0]
        self.assertEqual(
            self.doc.notifier_subject_suffix,
            message.subject[-len(self.doc.notifier_subject_suffix) :],
        )


class TestMissing(EdiNotifierCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiNotifier = cls.env["edi.notifier"]
        IrModel = cls.env["ir.model"]
        cls.doc_type_raw = cls.env.ref("edi.raw_document_type")
        cls.email_template = cls.env.ref("edi_notifier.email_template_edi_document_not_received")

        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc missing",
                "model_id": IrModel._get_id("edi.notifier.email.missing"),
                "doc_type_ids": [(6, False, cls.doc_type.ids)],
                "template_id": cls.email_template.id,
                "active": True,
                "safety": cls.safety,
            }
        )

    def test_cron_trigger_missing_not_reported(self):
        self.setup_cron(datetime.now() - timedelta(hours=1))
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_called_once()
        send_mail_mock.assert_called_with(
            self.email_template,
            self.doc_type.id,
            force_send=True,
            email_values=None,
        )

    def test_cron_trigger_missing_already_reported(self):
        dtime = datetime.now() - timedelta(hours=1)
        self.doc_type.x_last_checked_not_received = self._convert_time(dtime)
        self.setup_cron(dtime)
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_not_called()

    def test_cron_trigger_received(self):
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
        cls.email_template = cls.env.ref("edi_notifier.email_template_edi_document_not_received")
        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc missing",
                "model_id": IrModel._get_id("edi.notifier.email.missing.in.range"),
                "doc_type_ids": [(6, False, cls.doc_type.ids)],
                "template_id": cls.email_template.id,
                "lookback_hours": 3,
                "active": True,
                "safety": cls.safety,
            }
        )

    def test_dont_send_if_received(self):
        raw_doc = self.create_document(self.doc_type_raw)
        self.create_transfer(raw_doc)
        self.create_input_attachment(raw_doc, "res.users.csv")
        self.notifier.doc_type_ids = [(6, False, self.doc_type_raw.ids)]
        self.setup_cron(datetime.now())
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_not_called()

    def test_send_if_received_out_of_timeframe(self):
        raw_doc = self.create_document(self.doc_type_raw)
        self.create_transfer(raw_doc)
        self.create_input_attachment(raw_doc, "res.users.csv")
        self.notifier.doc_type_ids = [(6, False, self.doc_type_raw.ids)]
        self.setup_cron(datetime.now() + timedelta(hours=4))
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_called_with(
            self.email_template, self.doc_type_raw.id, force_send=True, email_values=None
        )

    def test_dont_send_if_received_within_timeframe(self):
        raw_doc = self.create_document(self.doc_type_raw)
        self.create_transfer(raw_doc)
        self.create_input_attachment(raw_doc, "res.users.csv")
        self.notifier.doc_type_ids = [(6, False, self.doc_type_raw.ids)]
        self.setup_cron(datetime.now() + timedelta(hours=1))
        with self.mock_send_mail() as send_mail_mock:
            self.cron.method_direct_trigger()
        send_mail_mock.assert_not_called()


class TestDisabledNotifier(EdiNotifierCase):
    """Disable email notifier test"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EdiNotifier = cls.env["edi.notifier"]
        IrModel = cls.env["ir.model"]
        cls.doc_type_raw = cls.env.ref("edi.raw_document_type")
        cls.email_template = cls.env.ref("edi_notifier.email_template_edi_document_not_received")
        cls.notifier = EdiNotifier.create(
            {
                "name": "Email on test doc missing",
                "model_id": IrModel._get_id("edi.notifier.email.missing.in.range"),
                "doc_type_ids": [(6, False, cls.doc_type.ids)],
                "template_id": cls.email_template.id,
                "lookback_hours": 3,
                "active": True,
                "safety": "edi.disable_edi_notifications",
            }
        )

    def test_no_email_sent_on_success_when_safety_set_to_false(self):
        with self.mock_send_mail() as send_mail_mock:
            self.assertTrue(self.doc.action_execute())
        self.assertEqual(self.doc.state, "done")
        send_mail_mock.assert_not_called()
