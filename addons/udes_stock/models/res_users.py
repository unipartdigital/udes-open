# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ResUser(models.Model):

    _inherit = "res.users"

    def _compute_allowed_picking_types(self):
        """ User's allowed picking types are the picking types allowed
            by its groups.
        """
        for user in self:
            user.u_picking_type_ids = user.mapped("groups_id.u_picking_type_ids")

    u_picking_type_ids = fields.Many2many(
        "stock.picking.type",
        string="Picking types",
        help="Picking types allowed for the user",
        compute=_compute_allowed_picking_types,
        readonly=True,
    )

    u_location_category_ids = fields.Many2many(
        comodel_name="stock.location.category", index=True, string="Location Category"
    )

    notification_type = fields.Selection(default="inbox")

    def get_user_warehouse(self):
        """ Get the warehouse of the user by chain of the company
        """
        Warehouse = self.env["stock.warehouse"]
        user = self.search([("id", "=", self.env.uid)])
        if not user:
            raise ValidationError(_("Cannot find user to get warehouse."))
        warehouse = Warehouse.search([("company_id", "=", user.company_id.id)])
        if not warehouse:
            raise ValidationError(_("Cannot find a warehouse for user"))
        if len(warehouse) > 1:
            raise ValidationError(_("Found multiple warehouses for user"))

        return warehouse

    def get_user_location_categories(self):
        """ Get the location categories of the user
        """
        user = self.search([("id", "=", self.env.uid)])
        if not user:
            raise ValidationError(_("Cannot find user to get location categories."))

        return user.u_location_category_ids

    def set_user_location_categories(self, category_ids):
        """ Set the location categories of the user
        """
        LocationCategory = self.env["stock.location.category"]
        user = self.search([("id", "=", self.env.uid)])
        if not user:
            raise ValidationError(_("Cannot find user to set location categories."))

        categories = LocationCategory.browse(category_ids).exists()
        miss_ids = set(category_ids) - set(categories.ids)
        if len(miss_ids) > 0:
            raise ValidationError(_("Cannot find some location categories ids: %s") % miss_ids)

        user.sudo().u_location_category_ids = categories

        return True

    def unassign_pickings_from_users(self, **kwargs):
        """Unassign users from a picking, to be overridden"""
        return

    def assign_picking_to_users(self, picking):
        """Assign a picking to user(s) in self, to be overridden"""
        return
