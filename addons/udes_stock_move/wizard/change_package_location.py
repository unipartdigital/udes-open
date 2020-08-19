# -*- coding: utf-8 -*-
from odoo import models, api, fields, _


class ChangePackageLocation(models.TransientModel):
    _name = "udes_stock_move.change_package_location"

    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Picking type",
        required=True,
        default=lambda self: self._default_picking_type(),
    )

    reference = fields.Char("Reference")

    location_dest_id = fields.Many2one(
        "stock.location", string="New destination location",
    )

    def _default_picking_type(self):
        """ Returns the Internal Transfer picking type """
        Users = self.env["res.users"]
        warehouse = Users.get_user_warehouse()
        return warehouse.int_type_id

    def create_picking(self):
        Package = self.env["stock.quant.package"]

        self.ensure_one()

        packages = Package.browse(self.env.context["active_ids"])
        packages.assert_not_reserved()

        params = {}
        if self.location_dest_id:
            params["location_dest_id"] = self.location_dest_id.id
        if self.reference:
            params["origin"] = self.reference

        new_picking = packages.create_picking(
            self.picking_type_id, confirm=True, assign=True, **params
        )

        return self.open_stock_picking_form_view(new_picking)

    def open_stock_picking_form_view(self, picking):
        picking.ensure_one()

        view_id = self.env.ref("stock.view_picking_form").id
        return {
            "name": _("Internal Transfer"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "stock.picking",
            "views": [(view_id, "form")],
            "view_id": view_id,
            "res_id": picking.id,
        }
