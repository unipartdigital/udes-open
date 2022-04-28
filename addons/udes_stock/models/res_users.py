from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.addons.udes_common.models.fields import PreciseDatetime
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

NON_ASSIGNABLE_STATES = ("draft", "done", "cancel")


class ResUser(models.Model):
    _inherit = "res.users"

    u_picking_id = fields.Many2one(
        "stock.picking",
        string="Assigned Picking",
        help="The picking a user is currently assigned to",
        readonly=True,
    )
    u_picking_assigned_time = PreciseDatetime(
        string="User Time Started",
        help="Precise time with microseconds when the user got assigned to the picking.",
        readonly=True,
        copy=False,
    )

    @api.model
    def get_user_warehouse(self, aux_domain=None):
        """Get the warehouse(s) of the user by chain of the company
        :kwargs:
            - aux_domain:
                If specified must return a single warehouse, if want a subset
                of warehouses then don't specify the aux_domain and filter result
        :returns: Warehouse(s), or a singular warehouse if aux_domain not None
        """
        Warehouse = self.env["stock.warehouse"]

        user = self.env.user
        if user.id != SUPERUSER_ID:
            user = self.search([("id", "=", user.id)])
            if not user:
                raise ValidationError(_("Cannot find user"))

        domain = [("company_id", "=", user.company_id.id)]
        if aux_domain is not None:
            domain += aux_domain
        warehouse = Warehouse.search(domain)
        if not warehouse:
            raise ValidationError(_("Cannot find a warehouse for user"))
        if len(warehouse) > 1 and aux_domain is not None:
            raise ValidationError(
                _(
                    "Found multiple warehouses for user, "
                    + "the aux_domain is specifying multiple warehouses or cannot be correct!"
                )
            )
        return warehouse

    def assign_picking_to_users(self, picking):
        """
        Assign a picking to user(s) in self
        """
        picking.ensure_one()
        picking_type = picking.picking_type_id

        # Find the users to assign
        users_to_assign = self.filtered(lambda u: u.u_picking_id != picking)
        if users_to_assign:
            if picking.state in NON_ASSIGNABLE_STATES:
                _logger.warning(
                    _("Cannot assign users %s to picking %s as it is in state %s")
                    % (self.mapped("name"), picking.name, picking.state)
                )
            elif len(self) > 1 and not picking_type.can_handle_multiple_users():
                _logger.warning(
                    _("Cannot assign users %s to picking %s as picking type %s only allows one user")
                    % (self.mapped("name"), picking.name, picking_type.name)
                )
            else:
                # Unassign the current users from their current (different) picking
                users_to_assign.unassign_pickings_from_users(new_picking=picking)
                # Kick out any users from the current picking if needed
                # Do not kick the current users in self out as they are already unassigned
                # from their own pickings.
                # NOTE: We could check here if there are any users in the picking, and kick them
                # out if needed, but instead we just extend unassign_users, as this
                # is needed when closing batches or if we extend the behaviour of multiple users
                # working on a picking.
                picking.unassign_users(skip_users=users_to_assign)
                users_to_assign._assign_picking_to_users(picking)

    def _assign_picking_to_users(self, picking):
        """Placing into a method in order to be able to inherit and change behaviour if needed.
        If the picking has never been started, update the start time."""
        now = PreciseDatetime.now()
        self.sudo().write(
            {"u_picking_id": picking.id, "u_picking_assigned_time": now})
        if not picking.u_date_started:
            picking.write({"u_date_started": now})

    def unassign_pickings_from_users(self, new_picking=False):
        """Finding users that need to be unassigned"""
        users_to_unassign = self.filtered(
            lambda u: u.u_picking_id and u.u_picking_id != new_picking
        )
        users_to_unassign._unassign_pickings_from_user()

    def _unassign_pickings_from_user(self):
        """
        Unassigning pickings from users.
        Placing into a method in order to be easier to inherit
        """
        self.sudo().write({"u_picking_id": False, "u_picking_assigned_time": False})
