from odoo import fields, models, api

EXTRA_FIELDS = {
    "u_user_id",
    "u_location_id",
    "u_vehicle_arrival_date",
    "u_week",
    "u_unloading_start_date",
    "u_unloading_end_date",
    "u_vehicle_type",
    "u_unloading_time_taken",
    "u_trailer_number",
    "u_lane_number",
    "u_pallet_count",
    "u_stillage_count",
    "u_box_count",
    "u_is_planned",
    "u_is_late",
    "u_is_fast_track",
    # backloading fields
    "u_is_backload",
    "u_backload_supplier",
    "u_backload_pallet_count",
    "u_backload_stillage_count",
    "u_backload_cover_count",
    "u_backload_reject_count",
    "u_backload_start_date",
    "u_backload_end_date",
    "u_backload_time_taken",
}


class StockPicking(models.Model):

    _inherit = "stock.picking"

    u_is_delivery_control = fields.Boolean(
        related="picking_type_id.u_is_delivery_control", readonly=1
    )
    u_extras_id = fields.Many2one("stock.picking.extras", copy=False)
    # Unloading Fields
    u_user_id = fields.Many2one("res.users", related="u_extras_id.user_id",)
    u_location_id = fields.Many2one("stock.location", related="u_extras_id.location_id")
    u_vehicle_arrival_date = fields.Datetime(related="u_extras_id.vehicle_arrival_date",)
    u_week = fields.Integer(related="u_extras_id.week")
    u_unloading_start_date = fields.Datetime(related="u_extras_id.unloading_start_date")
    u_unloading_end_date = fields.Datetime(related="u_extras_id.unloading_end_date")
    u_unloading_time_taken = fields.Float(readonly=True, related="u_extras_id.unloading_time_taken")
    u_vehicle_type = fields.Many2one(
        "stock.picking.vehicle.type", related="u_extras_id.vehicle_type"
    )
    u_trailer_number = fields.Char(related="u_extras_id.trailer_number")
    u_lane_number = fields.Char(related="u_extras_id.lane_number")
    u_pallet_count = fields.Integer(related="u_extras_id.pallet_count")
    u_stillage_count = fields.Integer(related="u_extras_id.stillage_count")
    u_box_count = fields.Integer(related="u_extras_id.box_count")
    u_is_planned = fields.Boolean(related="u_extras_id.is_planned",)
    u_is_late = fields.Boolean(related="u_extras_id.is_late",)
    u_is_fast_track = fields.Boolean(related="u_extras_id.is_fast_track",)

    # Backloading Fields
    u_is_backload = fields.Boolean(related="u_extras_id.is_backload",)
    u_backload_supplier = fields.Many2one(
        "res.partner",
        default=lambda self: self._default_u_supplier_id(),
        related="u_extras_id.backload_supplier",
    )
    u_backload_pallet_count = fields.Integer(related="u_extras_id.backload_pallet_count",)
    u_backload_stillage_count = fields.Integer(related="u_extras_id.backload_stillage_count",)
    u_backload_cover_count = fields.Integer(related="u_extras_id.backload_cover_count",)
    u_backload_reject_count = fields.Integer(related="u_extras_id.backload_reject_count",)
    u_backload_start_date = fields.Datetime(related="u_extras_id.backload_start_date")
    u_backload_end_date = fields.Datetime(related="u_extras_id.backload_end_date")
    u_backload_time_taken = fields.Float(related="u_extras_id.backload_time_taken")

    _sql_constraints = [
        (
            "extras_id_uniq",
            "UNIQUE (u_extras_id)",
            "You can not have two pickings associated with the same picking extras!",
        )
    ]

    def _create_picking_extras_data(self, values):
        """ Create a transport information for each picking that doesn't
            have it.
        """
        PickingExtras = self.env["stock.picking.extras"]
        filtered_extras = {k[2:]: values[k] for k in EXTRA_FIELDS if k in values and values[k]}
        if filtered_extras:
            for record in self:
                if not record.u_extras_id:
                    filtered_extras["picking_ids"] = [(4, record.id)]
                    PickingExtras.create(filtered_extras)
                else:
                    record.u_extras_id.write(filtered_extras)
            values = {k: v for k, v in values.items() if k not in EXTRA_FIELDS}

        return values

    @api.multi
    def write(self, values):
        values = self._create_picking_extras_data(values)
        res = super(StockPicking, self).write(values)
        return res

    @api.model
    def create(self, values):
        res = super(StockPicking, self).create(values)
        res._create_picking_extras_data(values)
        return res

    @api.model
    def _default_u_supplier_id(self):
        return self.partner_id
