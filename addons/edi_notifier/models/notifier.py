import logging
from datetime import datetime
from odoo.tools import config
from odoo import fields, api, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


NOT_SELECTABLE = {
    "edi.notifier.model",
    "edi.notifier.email",
    "edi.notifier.email.state",
}


class IrModel(models.Model):
    _inherit = "ir.model"

    is_edi_notifier = fields.Boolean(
        string="EDI Notifier Model", default=False, help="This is an EDI notifier model"
    )

    def _reflect_model_params(self, model):
        vals = super()._reflect_model_params(model)
        vals["is_edi_notifier"] = model._name not in NOT_SELECTABLE and issubclass(
            type(model), self.pool["edi.notifier.model"]
        )
        if vals["is_edi_notifier"] and vals["name"] == vals["model"]:
            vals["name"] = " ".join(["EDI"] + [x.capitalize() for x in vals["name"].split(".")[1:]])

        return vals


class ServerActions(models.Model):
    """Add EDI Transfer option in server actions"""

    _inherit = "ir.actions.server"

    state = fields.Selection(selection_add=[("edi_notifier", "EDI Notifier")])
    edi_notifier_id = fields.Many2one(
        "edi.notifier", string="EDI Notifier", index=True, ondelete="cascade"
    )

    @api.model
    def run_action_edi_notifier_multi(self, action, eval_context=None):
        """Run EDI Notifer server action"""
        # pylint: disable=unused-argument
        if action.edi_notifier_id:
            _logger.info("Running notifier {} via cron".format(action.edi_notifier_id.id))
            action.edi_notifier_id.notify("cron")


class EdiNotifier(models.Model):
    _name = "edi.notifier"
    _description = "EDI Notifier"

    name = fields.Char(string="Name", required=True, index=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Notifier type",
        domain=[("is_edi_notifier", "=", True)],
        required=True,
        index=True,
    )

    lookback_hours = fields.Integer(
        string="Look back hours",
        help="The number of hours in the past for checking transfer arrival",
    )

    # configurable safety catch
    safety = fields.Char(
        string="Safety Catch",
        help="""Configuration file option required for operation.
        If present, this option must have a truthy value within the
        local configuration file to enable Email notifications to be sent out.
        """,
    )

    @api.depends("model_id")
    def _compute_model_name(self):
        self.model_name = self.model_id.name or ""

    # This field is to be used in the views for selecting which fields are
    # visible/required
    model_name = fields.Char(string="Model Name", compute=_compute_model_name)

    doc_type_ids = fields.Many2many(
        "edi.document.type",
        column1="notifier_id",
        column2="doc_id",
        string="Document Types",
    )
    template_id = fields.Many2one("mail.template", domain=[("is_edi_template", "=", True)])
    cron_ids = fields.One2many(
        "ir.cron",
        "edi_notifier_id",
        domain=[("state", "=", "edi_notifier")],
        string="Schedule",
    )
    include_issues = fields.Boolean(string="Include issues", default=False)
    include_notes = fields.Boolean(string="Include notes", default=False)
    include_attachments = fields.Selection(
        selection=[("all", "All"), ("input", "Input"), ("output", "Output"), (False, "None")],
        default=False,
        string="Include attachments",
    )

    @api.depends("cron_ids")
    def _compute_cron_count(self):
        for rec in self:
            rec.cron_count = len(self.cron_ids)

    cron_count = fields.Integer(compute=_compute_cron_count)
    active = fields.Boolean(default=True)

    @api.depends("model_id")
    def _compute_can_use_crons(self):
        for notifier in self:
            if notifier.model_id:
                model = self.env[notifier.model_id.model]
                notifier.can_use_crons = model.can_use_crons
            else:
                notifier.can_use_crons = False

    can_use_crons = fields.Boolean(compute=_compute_can_use_crons)

    @api.onchange("doc_type_ids")
    @api.constrains("doc_type_ids")
    def check_for_not_doc_type(self):
        if len(self.doc_type_ids) == 0:
            self.active = False

    @api.constrains("active")
    def _check_if_can_set_active(self):
        if len(self.doc_type_ids) == 0 and self.active:
            self.active = False
            raise UserError(_("Active can not be set to true if there is no document types"))

    @api.onchange("active")
    def _check_if_can_set_active_ui(self):
        try:
            self._check_if_can_set_active()
        except UserError as err:
            # Throwing the user error doesn't reset the value of active
            # this forces the referesh of the value
            return {"warning": {"title": "Error", "message": err.name}}
        return None

    @api.multi
    def action_view_cron(self):
        """View scheduled jobs"""
        self.ensure_one()
        action = self.env.ref("edi.cron_action").read()[0]
        action["domain"] = [
            ("state", "=", "edi_notifier"),
            ("edi_notifier_id", "=", self.id),
        ]
        action["context"] = {
            "default_model_id": self.env["ir.model"]._get_id("edi.notifier"),
            "default_state": "edi_notifier",
            "default_edi_notifier_id": self.id,
            "default_numbercall": -1,
            "default_interval_type": "days",
            "create": True,
        }
        return action

    @api.multi
    def check_edi_notifications_enabled(self):
        """Check safety config parameter is present and return True if it's enable, otherwise False."""
        self.ensure_one()
        if self.safety:
            section, _sep, key = self.safety.rpartition(".")
            if config.get_misc(section or self._name, key):
                return True
        _logger.info(
            "%s %s disabled, enable by configuring safety.",
            self._name,
            self.name,
        )
        return False

    @api.multi
    def notify(self, event_type, recs=None):
        """Check for edi notification safety"""
        for notifier in self:
            if notifier.check_edi_notifications_enabled():
                if notifier.active:
                    self.env[notifier.model_id.model].notify(notifier, event_type, recs)

    @api.onchange("model_id")
    @api.depends("model_id")
    def set_mail_template_domain(self):
        if self.model_id:
            notifier = self.env[self.model_id.model]
            if hasattr(notifier, "get_email_model"):
                model = notifier.get_email_model().model
                if self.template_id and self.template_id.model != model:
                    self.template_id = False
                return {
                    "reload": True,
                    "nodestroy": True,
                    "domain": {
                        "template_id": [
                            ("is_edi_template", "=", True),
                            ("model", "=", notifier.get_email_model().model),
                        ],
                    },
                }
            elif self.template_id:
                self.template_id = False
                return {
                    "reload": True,
                    "nodestroy": True,
                }


class EdiNotifierModel(models.AbstractModel):
    _name = "edi.notifier.model"
    _description = "EDI Notifier Base Model"

    is_edi_notifier = True
    can_use_crons = False

    def _should_notify(self, notifier, event_type, _rec):
        """Returns if the notifier should handle record"""
        raise NotImplementedError

    def filter_records(self, notifier, event_type, recs):
        """Yields only records that should be handled"""
        return recs.filtered(lambda x: self._should_notify(notifier, event_type, x))

    @api.multi
    def _notify(self, notifier, event_type, _recs):
        """Does the action of notifying"""
        raise NotImplementedError

    @api.multi
    def _get_notes(self, rec):
        """Get notes related to a record"""
        rec.ensure_one()
        return self.env["mail.message"].search([("model", "=", rec._name), ("res_id", "=", rec.id)])

    @api.multi
    def _get_issues(self, rec):
        """Get issues from a record"""
        try:
            return rec.issue_ids
        except AttributeError:
            return None

    @api.multi
    def _get_attachments(self, rec):
        attachments = self._get_input_attachments(rec)
        attachments |= self._get_output_attachments(rec)
        return attachments

    @api.multi
    def _get_input_attachments(self, rec):
        return rec.input_ids

    @api.multi
    def _get_output_attachments(self, rec):
        return rec.output_ids

    @api.multi
    def notify(self, notifier, event_type, recs):
        """Filter records and send them for notification"""
        recs = self.filter_records(notifier, event_type, recs)
        self._notify(notifier, event_type, recs)
