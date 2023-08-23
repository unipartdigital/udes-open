from odoo import models, fields, _, api
from odoo.exceptions import AccessError, UserError, ValidationError

from lxml.html.clean import Cleaner

import logging
_logger = logging.getLogger(__name__)

HTML_TAGS_PREVENTED = ['a', 'script']

class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _message_create(self, values_list):
        """Extend _message_create to strip specified tags from the message body"""
        if not isinstance(values_list, (list)):
            values_list = [values_list]

        for vals in values_list:
            body_content = vals.get('body', False)
            #NOTE: not easy to distinguish email/Send message/Log note
            #Strip prevented html tags before storing to DB
            if '<' in body_content and '>' in body_content:
                vals['body'] = self._strip_prevented_html_tags(body_content)

        return super(MailThread, self)._message_create(values_list)

    def _strip_prevented_html_tags(self, html_text):
        """
        Remove specified tags from a html text.
        param: html_text: str() representation of html contents.
        """
        cleaner = Cleaner(javascript=True, scripts=True, remove_tags=HTML_TAGS_PREVENTED)
        return cleaner.clean_html(html_text)
