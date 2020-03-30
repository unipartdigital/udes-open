# -*- coding: utf-8 -*-
import logging

from odoo import api, models, fields, SUPERUSER_ID
from odoo.exceptions import AccessError
from odoo.tools.translate import _
from odoo.http import root, request

_store = root.session_store
_logger = logging.getLogger(__name__)


class Users(models.Model):
    _inherit = "res.users"

    u_restrict_to_single_session = fields.Boolean(
        string="Restrict user account to single login session", default=False
    )

    @classmethod
    def is_user_only_allowed_one_session(cls, uid):
        if request and request.db:
            return request.env["res.users"].browse(uid).u_restrict_to_single_session

        with cls.pool.cursor() as cr:
            self = api.Environment(cr, uid, {})[cls._name]
            return self.env["res.users"].browse(uid).u_restrict_to_single_session

    @classmethod
    def authenticate(cls, db, *args, **kwargs):
        """ Override to clear all previous sessions if authenticated """
        uid = super().authenticate(db, *args, **kwargs)

        if uid and cls.is_user_only_allowed_one_session(uid):
            sessions = {sid: _store.get(sid) for sid in _store.list()}
            for sid, session in filter(
                lambda x: x[1].uid == uid and x[1].db == db, sessions.items()
            ):
                _store.delete(session)
        return uid

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
        group_trusted_user = self.env.ref("udes_security.group_trusted_user")
        self._check_is_admin(values, group_trusted_user)

    def _check_is_admin(self, values, group):

        values = self._remove_reified_groups(values)

        # Only the root user can add or remove the Trusted User group
        if self.env.uid != SUPERUSER_ID and "groups_id" in values:
            # Validate the many2many write to check that the
            # Trusted User group is not being added or removed.
            disallowed = False
            for act in values["groups_id"]:
                if act[0] in (0, 1, 2):
                    pass
                elif act[0] in (3, 4):
                    # Remove and add group
                    disallowed |= act[1] == group.id
                elif act[0] == 5:
                    # Remove all groups
                    disallowed |= group in self.mapped("groups_id")
                elif act[0] == 6:
                    # Replace all groups
                    for user in self:
                        disallowed |= (group in user.groups_id) != (group.id in act[2])
                else:
                    raise ValueError(_("Unknown operation in many2many write for groups_id"))

                if disallowed:
                    break

            if disallowed:
                _logger.warning("User %s tried to change %s group." % (self.env.uid, group.name))
                raise AccessError(
                    _(
                        "%s cannot be added or removed due to security "
                        "restrictions. Please contact your system "
                        "administrator."
                    )
                    % group.name
                )
