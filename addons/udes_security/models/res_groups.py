# -*- coding: utf-8 -*-
import logging

from odoo import api, models, SUPERUSER_ID
from odoo.exceptions import AccessError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


security_groups = [
    'udes_security.group_trusted_user',
    'udes_security.group_debug_user',
]

class Groups(models.Model):
    _inherit = 'res.groups'

    @api.multi
    def write(self, values):
        for group in security_groups:
            group_user = self.env.ref(group)

            # Only the root user can add or remove the Trusted User group
            self._check_is_admin(values, group_user)

        res = super(Groups, self).write(values)
        return res

    def _check_is_admin(self, values, group):
        ''' To be used when only admin user is allowed to change add/remove
            the security group.
        '''

        if (group in self and
            self.env.uid != SUPERUSER_ID and
            len(values.get('users', [])) > 0):
            _logger.warning(
                'User %s tried to change %s group for users %s.' %
                (self.env.uid, group.name, values.get('users')))
            raise AccessError(
                _('%s cannot be added or removed due to security '
                  'restrictions. Please contact your system administrator.') %
                group.name
            )
