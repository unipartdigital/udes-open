import logging

from odoo import models, fields
from odoo.exceptions import AccessError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class Groups(models.Model):
    _inherit = "res.groups"

    u_required_group_id_to_change = fields.Many2one(
        "res.groups",
        "Required Group to Change on User",
        readonly=True,
        help="Group the active user needs in order to set/remove this group on a user record.",
    )

    def write(self, vals):
        """ Override to ensure active user has permission to change users in group """
        if not self.env.user._is_superuser_or_admin():
            self._check_user_group_modify(vals)
        return super(Groups, self).write(vals)

    def _check_user_group_modify(self, vals):
        """ Raise error if active user does not have permission to modify group users """
        users = vals.get("users")

        if not self.env.su and users:
            active_user_groups = self.env.user.groups_id
            groups_to_check = self.filtered("u_required_group_id_to_change")

            for group in groups_to_check:
                if group.u_required_group_id_to_change not in active_user_groups:
                    _logger.warning(
                        f"User {self.env.uid} tried to change {group.full_name} group for users "
                        f"{users}."
                    )
                    raise AccessError(
                        _(
                            "%s cannot be added or removed due to security "
                            "restrictions. Please contact your system administrator."
                        )
                        % group.full_name
                    )

    def set_required_group_to_change_to_self(self, overwrite=False):
        """
        For each group in self, set required group to change to itself.

        If overwrite is not True, the group will not be updated if it already
        has a required group to change set.
        """
        for group in self.filtered(lambda g: overwrite or not g.u_required_group_id_to_change):
            group.write({"u_required_group_id_to_change": group.id})
