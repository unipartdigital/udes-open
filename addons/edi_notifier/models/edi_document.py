import logging

from odoo import fields, api, models

_logger = logging.getLogger(__name__)


class EdiDocumentType(models.Model):
    _inherit = "edi.document.type"

    notifier_ids = fields.Many2many(
        "edi.notifier", column1="doc_id", column2="notifier_id", string="Notifiers"
    )

    x_last_not_received_notification = fields.Datetime("Last not received notification")


class EdiDocument(models.Model):
    _inherit = "edi.document"

    @api.multi
    def action_execute(self):
        """Extend action execute to call notifiers"""
        super().action_execute()
        if self.doc_type_id.notifier_ids:
            _logger.info("Calling notifiers")
            self.doc_type_id.notifier_ids.notify(self)
