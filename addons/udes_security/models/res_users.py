# -*- coding: utf-8 -*-
import logging

from odoo import api, models, fields, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _
from odoo.http import root, request

from . import res_groups

_store = root.session_store
_logger = logging.getLogger(__name__)


class Users(models.Model):
    _inherit = "res.users"

    u_restrict_to_single_session = fields.Boolean(
        string="Restrict user account to single login session", default=False
    )
    u_desktop_readonly = fields.Boolean(
        string="View Only Desktop User",
        default=False,
        help="""
        If set the user cannot create/edit/delete any records in the desktop UI,
        regardless of other permissions.

        Note: This doesn't restrict any operations that take place outside of the desktop UI,
              e.g. via Odoo RPC
        """,
    )

    @classmethod
    def is_user_only_allowed_one_session(cls, uid):
        if request and request.db:
            user = request.env["res.users"].browse(uid)
            return user.sudo().u_restrict_to_single_session

        with cls.pool.cursor() as cr:
            self = api.Environment(cr, uid, {})[cls._name]
            return self.env["res.users"].browse(uid).u_restrict_to_single_session

    @classmethod
    def authenticate(cls, db, *args, **kwargs):
        """Override to clear all previous sessions if authenticated"""
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
        self._check_user_group_grant(values)
        self._check_view_only_user(values)

        user = super(Users, self).create(values)
        return user

    @api.multi
    def write(self, values):
        self._check_user_group_grant(values)
        self._check_view_only_user(values)

        res = super(Users, self).write(values)
        return res

    def _check_user_group_grant(self, values):
        for group in res_groups.security_groups:
            group_user = self.env.ref(group)
            self._check_is_admin(values, group_user)

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

    @api.model_cr_context
    def _auth_timeout_enabled(self):
        """Pluggable method to check if session timeout is enabled"""
        IrConfigParameter = self.env["ir.config_parameter"]

        auth_timeout_enabled_parameter = IrConfigParameter.get_param(
            "inactive_session_time_out_enabled"
        )
        return auth_timeout_enabled_parameter == "True"

    @api.model
    def _auth_timeout_check(self):
        """Override to not carry out timeout check if system parameter is disabled"""
        auth_timeout_enabled = self._auth_timeout_enabled()

        if not auth_timeout_enabled:
            return
        else:
            return super(Users, self)._auth_timeout_check()

    def _check_view_only_user(self, vals):
        """
        Raise a UserError if either of the following are true:

            1. Active user is not an admin or debug user
            2. User being updated is an admin or debug user
        """

        def _log_warning(user_ids):
            _logger.warning(
                "User %s tried to set user(s) %s as a View Only Desktop User."
                % (self.env.uid, user_ids)
            )

        if "u_desktop_readonly" in vals:
            user_ids = self.mapped("id")

            if not self.env.uid == SUPERUSER_ID and not self.env.user.has_group(
                "udes_security.group_debug_user"
            ):
                _log_warning(user_ids)
                raise UserError(
                    _("Only Admin and Debug users can set/unset View Only Desktop User")
                )

            new_user_rec = not bool(self.mapped("id"))
            desktop_readonly = vals["u_desktop_readonly"]

            # u_desktop_readonly is set to False by default for new user records
            if not new_user_rec or (new_user_rec and desktop_readonly):
                if SUPERUSER_ID in user_ids or self.filtered(
                    lambda u: u.has_group("udes_security.group_debug_user")
                ):
                    _log_warning(user_ids)
                    raise UserError(
                        _("Admin and Debug users cannot be set to View Only Desktop User")
                    )


class ChangePasswordUser(models.TransientModel):
    _inherit = "change.password.user"

    def change_password_button(self):
        """
        Check that the active user has permission to change the password of the users within
        self.

        Log which user changed the passwords for the selected users.
        """
        self._check_user_password_grant()
        # Run as sudo as password managers do not explicitly have sufficient rights to edit users
        self_sudo = self.sudo()
        res = super(ChangePasswordUser, self_sudo).change_password_button()

        _logger.info(
            "User %s changed the password of user(s): %s."
            % (self.env.uid, self.mapped("user_id").ids)
        )

        return res

    def _log_and_raise_access_error(self, users):
        """
        Log and Raise and Access Error as the user tried to change the password for a user
        without the appropriate permissions.

        :args:
            - users: Recordset of `res.users` which the active user tried to change
                        the passwords of
        """
        _logger.warning(
            "User %s tried to change the password of user(s): %s." % (self.env.uid, users.ids)
        )
        raise AccessError(_("You do not have permission to change password of selected user(s)."))

    def _check_user_password_grant(self):
        """
        Ensure that active user has permission to change the passwords of users in self.

        Raise an AccessError and log a warning if either:

        1. A non-Password Manager user tries to change someone else's password
        2. A non-admin/debug user (inc. Password Manager) tries to change the password of
           an admin or debug user.
        """
        users = self.mapped("user_id")
        # Don't need to check for permission if admin or user is just changing their own password
        if self.env.uid != SUPERUSER_ID and users != self.env.user:
            pwd_manager_group = "udes_security.group_password_manager"
            debug_group = "udes_security.group_debug_user"

            pwd_manager = self.env.user.has_group(pwd_manager_group)
            debug_user = self.env.user.has_group(debug_group)

            if not pwd_manager:
                # Non-password manager is trying to change the password of another user
                self._log_and_raise_access_error(users)

            if not debug_user:
                admin_debug_users_to_update = users.filtered(
                    lambda u: u.id == SUPERUSER_ID or u.has_group(debug_group)
                )
                if admin_debug_users_to_update:
                    # Non-admin/debug user is trying to change the password of an admin/debug user
                    self._log_and_raise_access_error(admin_debug_users_to_update)
