# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class ChangeQuantLocation(models.TransientModel):
    _name = 'change_quant_location'

    def _default_stock(self):
        Users = self.env['res.users']
        warehouse = Users.get_user_warehouse()
        return warehouse.lot_stock_id.id

    location_dest_id = fields.Many2one(
        'stock.location',
        string='New destination location',
    )

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Optional picking type',
    )
    reference = fields.Char('Reference')

    @api.multi
    def check_reserved(self):
        """Check if we are moving reserved packages and if that is permitted"""
        Package = self.env["stock.quant.package"]

        self.ensure_one()
        packages = Package.browse(self.env.context['active_ids'])
        quants = packages._get_contained_quants()
        reserved = any([quant.reserved_quantity for quant in quants])
        if reserved:
            # Check if we allow the creation of pickings for reserved packages
            if self._check_reserved_packages_permitted():
                # If permitted, make them confirm they want to move reserved packages
                return {
                    "name": _("Create Picking for Reserved Package(s)?"),
                    "type": "ir.actions.act_window",
                    "view_type": "form",
                    "view_mode": "form",
                    "res_model": "change_quant_location",
                    "views": [
                        (self.env.ref("udes_stock.view_move_reserved_package_check").id, "form")
                    ],
                    "view_id": self.env.ref("udes_stock.view_move_reserved_package_check").id,
                    "target": "new",
                    "res_id": self.id,
                    "context": self.env.context,
                }
            else:
                # Otherwise use existing functionality to show full details on error
                quants.assert_not_reserved()

        # If nothing is reserved we can directly create the picking
        return self.create_picking()

    def _check_reserved_packages_permitted(self):
        """Check if a user is allowed to create a picking for reserved packages.
        Returns a boolean.
        """
        user_allowed = self.env.user.has_group("udes_stock.group_manage_reserved_packages")
        warehouse = self.env.user.get_user_warehouse()
        return warehouse.u_allow_create_picking_reserved_package and user_allowed

    @api.multi
    def create_picking(self):
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']

        self.ensure_one()
        packages = Package.browse(self.env.context["active_ids"])
        quants = packages._get_contained_quants()

        # Check if we are allowed to move the reserved quants
        total_quantity_reserved = sum(quants.mapped("reserved_quantity"))
        if total_quantity_reserved:
            if not self._check_reserved_packages_permitted():
                # If not allowed to move reserved packages use existing functionality
                # to show full details on error
                quants.assert_not_reserved()
            total_quantity = sum(quants.mapped("quantity"))
            if total_quantity != total_quantity_reserved:
                # If all quants are not fully reserved then error
                raise ValidationError(
                    _("Packages/Pallets must be either entirely reserved or unreserved.")
                )

        location = packages.mapped("location_id")
        if len(location) == 1:
            location_id = location.id
        else:
            location_id = self._default_stock()
        params = {
            "location_id": location_id,
            "picking_type_id": self.picking_type_id.id,
            "location_dest_id": (
                self.location_dest_id.id or self.picking_type_id.default_location_dest_id.id
            )
        }
        if self.reference:
            params['origin'] = self.reference

        # If quants are reserved move them to a new picking
        if total_quantity_reserved:
            # Create a new picking
            new_picking = Picking.create(params)
            movelines = packages.get_move_lines([("state", "=", "assigned")])
            if any(movelines.mapped("qty_done")):
                raise ValidationError(
                    _("Pickings cannot be created when movelines are partially complete.")
                )
            # Move the moves/movelines to the new picking
            for picking, mls in movelines.groupby("picking_id"):
                picking._backorder_movelines(mls=mls, dest_picking=new_picking)
        # Otherwise create a picking for the unreserved quants
        else:
            params["quant_ids"] = quants.ids
            new_picking = Picking.create_picking(**params)

        # NOTE: this picking may not contain all the packages.
        # If the picking type has refactoring set-up, other pickings
        # may be created as well.
        return new_picking.open_stock_picking_form_view()
