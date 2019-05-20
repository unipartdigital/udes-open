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
        if (self.env.uid != SUPERUSER_ID and
           'groups_id' in values):
            # Validate the many2many write to check that the
            # Trusted User group is not being added or removed.
            disallowed = False
            for act in values['groups_id']:
                if act[0] in (0, 1, 2):
                    pass
                elif act[0] in (3, 4):
                    # Remove and add group
                    disallowed |= act[1] == group_trusted_user.id
                elif act[0] == 5:
                    # Remove all groups
                    disallowed |= group_trusted_user in self.mapped('groups_id')
                elif act[0] == 6:
                    # Replace all groups
                    for user in self:
                        disallowed |= ((group_trusted_user in user.groups_id) !=
                                       (group_trusted_user.id in act[2]))
                else:
                    raise ValueError('Unknown operation in many2many write for groups_id')

                if disallowed:
                    break

            if disallowed:
                raise AccessError(_('Trusted Users cannot be added or removed due to security restrictions. Please contact your system administrator.'))
