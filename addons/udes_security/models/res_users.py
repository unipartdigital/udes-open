import logging
import re
from odoo import models, fields, _, api
from odoo.exceptions import AccessError, UserError
from odoo.http import root
from collections import namedtuple
from odoo.addons.udes_common.tools import RelFieldOps

_store = root.session_store
_logger = logging.getLogger(__name__)

complexity_rule = namedtuple("Rule", ["regex", "message"])


class ResUsers(models.Model):
    _inherit = "res.users"

    u_is_trusted_user = fields.Boolean(string="Trusted User?", compute="_compute_is_trusted_user")

    def _compute_is_trusted_user(self):
        """Set to True for user if they have trusted user security group, otherwise False"""
        for user in self:
            user.u_is_trusted_user = user.has_group("udes_security.group_trusted_user")

    @api.model
    def create(self, vals):
        """Override to check active user has permission to grant groups to new user"""
        self._check_user_group_modify(vals, new_user=True)
        user = super(ResUsers, self).create(vals)
        return user

    def write(self, vals):
        """
        Active user permissions checked when updating user groups
        """
        password = vals.get("password")
        if password:
            self._check_password_complexity(password)

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
        """
        Raise error if active user does not have permission to add/remove group from user.

        Superuser and admin are exempt from the checks.
        """
        Group = self.env["res.groups"]

        unreified_group_vals = self._remove_reified_groups(vals)

        if (
            "groups_id" in unreified_group_vals
            and not self.env.user._is_superuser_or_admin()
            and not self.env.su
        ):
            current_user_group_ids = self.groups_id.ids

            # Validate the many2many write to check that the
            # supplied user group is not being added or removed.
            disallowed_group = False
            for action in unreified_group_vals["groups_id"]:
                groups_to_check = Group.browse()
                operation = action[0]

                if operation in (RelFieldOps.Create, RelFieldOps.Update, RelFieldOps.Delete):
                    pass

                elif operation in (RelFieldOps.Remove, RelFieldOps.Add):
                    group_id = action[1]
                    group = Group.browse(group_id)

                    if group.u_required_group_id_to_change:
                        # If new user record, only check if the group is being added
                        # If a group is being removed,
                        # check if the user actually had that group already
                        if operation == 4 or (
                            not new_user and operation == 3 and group_id in current_user_group_ids
                        ):
                            groups_to_check = group

                elif operation == RelFieldOps.RemoveAll:
                    # Remove all groups
                    groups_to_check = self.mapped("groups_id").filtered(
                        "u_required_group_id_to_change"
                    )

                elif operation == RelFieldOps.Replace:
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
                        f"User {self.env.uid} tried to change {disallowed_group.full_name} group."
                    )
                    raise AccessError(
                        _(
                            "%s cannot be added or removed due to security restrictions. "
                            "Please contact your system administrator."
                        )
                        % disallowed_group.full_name
                    )

    def _check_password_complexity(self, password, raise_on_failure=True):
        """
        Returns True if supplied password passes complexity threshold

        If not, UserError is raised by default (raise_on_failure), otherwise False is returned
        """
        self.ensure_one()
        if not password:
            return True
        company_id = self.company_id

        length = company_id.u_minimum_password_length
        lower = company_id.u_minimum_password_lower
        upper = company_id.u_minimum_password_upper
        numeric = company_id.u_minimum_password_numeric
        special = company_id.u_minimum_password_special

        password_rules = (
            complexity_rule(
                regex="^.{%d,}$" % length,
                message="Your password must be at least %s characters in length" % length,
            ),
            complexity_rule(
                regex="^(.*?[a-z].*?){%s,}" % lower,
                message="Your password must contain at least %s lowercase characters (a-z)" % lower,
            ),
            complexity_rule(
                regex="^(.*?[A-Z].*?){%s,}" % upper,
                message="Your password must contain at least %s uppercase characters (A-Z)" % upper,
            ),
            complexity_rule(
                regex="^(.*?[0-9].*?){%s,}" % numeric,
                message="Your password must contain at least %s numerical digits (0-9)" % numeric,
            ),
            complexity_rule(
                regex="^(.*?[\\W_].*?){%s,}" % special,
                message="Your password must contain at least %s special characters such as (!@$[]{}_)"
                % special,
            ),
        )

        errors = []
        for rule in password_rules:
            if not re.search(rule.regex, password):
                errors.append(rule.message)

        if errors:
            if raise_on_failure:
                raise UserError("\r\n".join(["- " + _(e) for e in errors]))
            else:
                return False

        return True
