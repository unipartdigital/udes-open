# -*- coding: utf-8 -*-
import logging
from odoo import models, _

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def send_rfq_emails(self):
        '''Send draft RFQs via email'''

        Mail = self.env['mail.mail']
        RequestOrder = self.env['purchase.order']

        email_template = self.env.ref('purchase.email_template_edi_purchase')
        rfqs_to_send = RequestOrder.search([('state', '=', 'draft')])

        if rfqs_to_send:
            rfq_by_mail_id = {}
            for rfq in rfqs_to_send:
                # Generate message to send later
                mail_id = email_template.send_mail(rfq.id)
                rfq_by_mail_id[mail_id] = rfq

            mail = Mail.browse(rfq_by_mail_id.keys())
            # Actually sends it
            mail.send()

            # As it auto deletes, the exists() method returns False
            # but incase this changes I'll check state as well
            failed_messages_by_rfq = {rfq_by_mail_id[msg.id]: msg
                                      for msg in mail
                                      if msg.exists() and
                                      not msg.state == 'sent'}

            failed_rfqs = RequestOrder.union(*failed_messages_by_rfq.keys())
            sent_rfqs = (rfqs_to_send - failed_rfqs)

            if sent_rfqs:
                sent_rfqs.button_cancel()
                _logger.info(
                    _('Sent RFQ messages for RFQ ids (%s)')
                    % ', '.join(map(str, sent_rfqs.ids))
                )

            if failed_rfqs:
                _logger.info(
                    _('Failed to send RFQ messages for RFQ ids (%s)')
                    % ', '.join(map(str, failed_rfqs.ids))
                )
                for rfq in failed_rfqs:
                    rfq.message_post(
                        body=failed_messages_by_rfq[rfq].failure_reason,
                        content_subtype='plaintext'
                    )
