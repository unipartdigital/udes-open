# -*- coding: utf-8 -*-
import logging

from odoo import api, models, SUPERUSER_ID
from odoo.exceptions import AccessError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

class Users(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, values):
        self._check_trusted_user_grant(values)

        user = super(Users, self).create(values)
        return user

    @api.multi
    def write(self, values):
        self._check_trusted_user_grant(values)

        res = super(Users, self).write(values)
        return res

    def _check_trusted_user_grant(self, values):
        group_trusted_user = self.env.ref('udes_security.group_trusted_user')

        values = self._remove_reified_groups(values)

        # Only the root user can add or remove the Trusted User group
        for op, group_id in values.get('groups_id', []):
            if (group_id == group_trusted_user.id and
                self.env.uid != SUPERUSER_ID):
                raise AccessError(_('Trusted Users cannot be added or removed due to security restrictions. Please contact your system administrator.'))
