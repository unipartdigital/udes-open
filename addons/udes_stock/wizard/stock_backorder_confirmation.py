from odoo import api, fields, models, _


class StockBackorderConfirmation(models.TransientModel):
    _inherit = "stock.backorder.confirmation"

    u_disable_no_backorder_button = fields.Boolean(
        string="Disable `No Backorder` button",
        compute="_compute_disable_no_backorder_button",
        help="Hide the `No Backorder` button if a user must always create a backorder when "
        "validating a picking not fully available for that picking type.",
    )

    @api.depends("pick_ids")
    def _compute_disable_no_backorder_button(self):
        """Compute if the picking type must always create a backorder"""
        Users = self.env["res.users"]

        warehouse = Users.get_user_warehouse()
        picking_type = self.pick_ids.mapped("picking_type_id")
        picking_type.ensure_one()
        self.u_disable_no_backorder_button = (
            picking_type in warehouse.u_disable_no_backorder_button_picking_type_ids
        )
