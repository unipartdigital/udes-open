# -*- coding: utf-8 -*-
from odoo import api, models

import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def send_message_to_user(
        self, subject, body, recipients=None, related_rec=None, attachment=None, type="notification"
    ):
        """
        Utility method to create and send an odoo message to the
        current user, or to recipients.

        :param subject: Subject of the message.
        :param body: Body text of the message.
        :param recipients: List of res.user recipients. Defaults to current user.
        :param related_rec: Related record.
        :param attachment: ir.attachment to attach to the message.
        :param type: message type. Defaults to Odoo internal notification
        :return: None
        """
        Message = self.env["mail.message"]
        Notification = self.env["mail.notification"]

        if recipients is None:
            recipients = [self.env.user]

        _logger.info(
            "Message to: {RECIPIENTS}\n"
            "{SUBJECT}\n"
            "{BODY}\n"
            "Attached File: {ATTACHMENT}".format(
                RECIPIENTS=[u.name for u in recipients],
                SUBJECT=subject,
                BODY=body,
                ATTACHMENT=attachment.datas_fname or "None",
            )
        )

        info = {
            "message_type": type,
            "subject": subject,
            "record_name": subject,
            "body": body,
            "partner_ids": [(4, recip.partner_id.id) for recip in recipients],
        }

        if related_rec is not None:
            info.update({"model": related_rec._name, "res_id": related_rec.id})

        if attachment is not None:
            info.update({"attachment_ids": [(4, attachment.id, 0)]})

        msg = Message.create(info)

        if attachment is not None:
            attachment.write(
                {"res_model": msg._name, "res_id": msg.id, "res_name": msg.record_name}
            )

        for recip in recipients:
            Notification.create({"mail_message_id": msg.id, "res_partner_id": recip.partner_id.id})
