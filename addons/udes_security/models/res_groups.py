# -*- coding: utf-8 -*-
import logging

from odoo import api, models, SUPERUSER_ID
from odoo.exceptions import AccessError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

class Groups(models.Model):
    _inherit = 'res.groups'

    @api.multi
    def write(self, values):
        group_trusted_user = self.env.ref('udes_security.group_trusted_user')

        # Only the root user can add or remove the Trusted User group
        if (group_trusted_user in self and
            self.env.uid != SUPERUSER_ID and
            len(values.get('users', [])) > 0):
            raise AccessError(_('Trusted Users cannot be added or removed due to security restrictions. Please contact your system administrator.'))

        res = super(Groups, self).write(values)
        return res
