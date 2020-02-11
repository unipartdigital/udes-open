import logging
from datetime import datetime

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
            vals["name"] = " ".join(
                ["EDI"] + [x.capitalize() for x in vals["name"].split(".")[1:]]
            )

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
            _logger.info(
                "Running notifier {} via cron".format(action.edi_notifier_id.id)
            )
            action.edi_notifier_id.notify()


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
    template_id = fields.Many2one(
        "mail.template", domain=[("is_edi_template", "=", True)]
    )
    cron_ids = fields.One2many(
        "ir.cron",
        "edi_notifier_id",
        domain=[("state", "=", "edi_notifier")],
        string="Schedule",
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
            raise UserError(
                _("Active can not be set to true if there is no document types")
            )

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
    def notify(self, recs=None):
        for notifier in self:
            if notifier.active:
                self.env[notifier.model_id.model].notify(notifier, recs)

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

    def _should_notify(self, notifier, _rec):
        """Returns if the notifier should handle record"""
        raise NotImplementedError

    def filter_records(self, notifier, recs):
        """Yields only records that should be handled"""
        return recs.filtered(lambda x: self._should_notify(notifier, x))

    @api.multi
    def _notify(self, notifier, _recs):
        """Does the action of notifying"""
        raise NotImplementedError

    @api.multi
    def notify(self, notifier, recs):
        """Filter records and send them for notification"""
        self._notify(notifier, self.filter_records(notifier, recs))
