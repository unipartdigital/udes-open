import re
import base64
import logging
from odoo import models, fields, _, api, SUPERUSER_ID, http
from odoo.exceptions import Warning as UserError
from odoo.exceptions import AccessError
from odoo.http import root
from collections import namedtuple

_store = root.session_store
_logger = logging.getLogger(__name__)

complexity_rule = namedtuple("Rule", ["regex", "message"])


class ResUsers(models.Model):
    _inherit = "res.users"

    u_is_trusted_user = fields.Boolean(string="Trusted User?", compute="_compute_is_trusted_user")

    def _compute_is_trusted_user(self):
        """ Set to True for user if they have trusted user security group, otherwise False """
        for user in self:
            user.u_is_trusted_user = user.has_group("udes_security.group_trusted_user")

    @api.model
    def create(self, vals):
        """ Override to check active user has permission to grant groups to new user """
        self._check_user_group_modify(vals, new_user=True)
        user = super(ResUsers, self).create(vals)
        return user

    def write(self, vals):
        """
        Active user permissions checked when updating user groups
        """
        self._check_user_group_modify(vals)
        return super(ResUsers, self).write(vals)


    def _get_first_disallowed_user_group_modify(self, groups):
        """
        Check supplied groups and return first group that the active user doesn't have
        permission to add/remove from other users
        """
        disallowed_group = False
        active_user_groups = self.env.user.groups_id

        for group in groups:
            change_requires_group = group.u_required_group_id_to_change
            if change_requires_group not in active_user_groups:
                disallowed_group = group
                break

        return disallowed_group

    def _check_user_group_modify(self, vals, new_user=False):
        """ Raise error if active user does not have permission to add/remove group from user """
        Group = self.env["res.groups"]

        unreified_group_vals = self._remove_reified_groups(vals)

        if "groups_id" in unreified_group_vals and self.env.uid != SUPERUSER_ID:
            # Validate the many2many write to check that the
            # supplied user group is not being added or removed.
            disallowed_group = False
            for action in unreified_group_vals["groups_id"]:
                groups_to_check = Group.browse()
                operation = action[0]

                if operation in (0, 1, 2):
                    pass

                elif operation in (3, 4):
                    # Remove and add group
                    group_id = action[1]
                    group = Group.browse(group_id)

                    if group.u_required_group_id_to_change:
                        # If new user record, only check if the group is being added
                        if not new_user or operation == 4:
                            groups_to_check = group

                elif operation == 5:
                    # Remove all groups
                    groups_to_check = self.mapped("groups_id").filtered("u_required_group_id_to_change")

                elif operation == 6:
                    # Replace all groups
                    group_ids = action[2]
                    groups = Group.browse(group_ids)

                    added_groups_to_check = groups.filtered("u_required_group_id_to_change")
                    removed_groups_to_check = self.mapped("groups_id").filtered(
                        "u_required_group_id_to_change"
                    )

                    groups_to_check = (added_groups_to_check | removed_groups_to_check).filtered(
                        lambda g: g not in added_groups_to_check or g not in removed_groups_to_check
                    )

                else:
                    raise ValueError(_("Unknown operation in many2many write for groups_id"))

                disallowed_group = self._get_first_disallowed_user_group_modify(groups_to_check)

                if disallowed_group:
                    _logger.warning(
                        f"User {self.env.uid} tried to change {disallowed_group.name} group."
                    )
                    raise AccessError(
                        _(
                            "%s cannot be added or removed due to security restrictions. "
                            "Please contact your system administrator."
                        )
                        % disallowed_group.name
                    )

