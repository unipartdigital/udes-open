from odoo import api, fields, models, _
from ..misc import date_diff, validate_dates
from odoo.exceptions import ValidationError


class StockPickingExtras(models.Model):
    """
        Model to hold all extra fields of stock.picking object
    """

    _name = "stock.picking.extras"
    _description = "UDES Picking Extra Fields"

    picking_ids = fields.One2many(
        comodel_name="stock.picking", inverse_name="u_extras_id", string="Pickings"
    )
    loading_type = fields.Selection(
        [
            ("unload", "Unloading"),
            ("backload", "Backloading"),
            ("unload_backload", "Unloading and Backloading"),
        ],
        string="Select Loading Type",
    )

    # Common Fields
    user_id = fields.Many2one("res.users", string="User", help="Picking completed by user")
    vehicle_arrival_date = fields.Datetime("Arrival Date/Time", help="Arrival time of Vehicle")
    week = fields.Integer(compute="_compute_week", store=True, default=0)
    vehicle_type = fields.Many2one("stock.picking.vehicle.type")
    trailer_number = fields.Integer()
    is_planned = fields.Boolean(
        "Planned", help="Indicates whether the door control was planned or not", default=False
    )
    is_late = fields.Boolean(
        "Late", help="Indicates whether the unloading was late if booking slot set", default=False
    )
    is_fast_track = fields.Boolean(
        "Fast Track", help="Indicates whether the unloading has been fast tracked", default=False
    )

    # Unloading Fields
    is_unload = fields.Boolean(compute="_compute_loading_type")
    location_id = fields.Many2one("stock.location", domain=[("usage", "=", "internal")])
    unloading_start_date = fields.Datetime("Start Date/Time", help="Unloading start date/time")
    unloading_end_date = fields.Datetime("End Date/Time", help="Unloading completed date/time")
    unloading_time_taken = fields.Float(
        "Unloading Time HH:MM",
        compute="_compute_unloading_time_taken",
        store=True,
        readonly=True,
        help="The amount of time taken to complete unloading in HH:MM format",
    )
    lane_number = fields.Char()
    pallet_count = fields.Integer(default=0)
    stillage_count = fields.Integer(default=0)
    box_count = fields.Integer(default=0)

    # Back Loading Fields
    is_backload = fields.Boolean(compute="_compute_loading_type")
    backload_ids = fields.One2many(comodel_name="stock.picking.backload", inverse_name="extras_id")

    @api.multi
    @api.depends("vehicle_arrival_date")
    def _compute_week(self):
        """ Compute method of week field """
        for record in self:
            record.week = 0
            if record.vehicle_arrival_date:
                record.week = fields.Datetime.from_string(
                    record.vehicle_arrival_date
                ).isocalendar()[1]

    @api.multi
    @api.depends("unloading_start_date", "unloading_end_date")
    def _compute_unloading_time_taken(self):
        """ Compute Unloading time_taken field from unloading start and end date """
        for record in self:
            record.unloading_time_taken = 0
            if record.unloading_start_date and record.unloading_end_date:
                record.unloading_time_taken = date_diff(
                    record.unloading_start_date, record.unloading_end_date
                )

    @api.depends("loading_type")
    def _compute_loading_type(self):
        """Compute is_backloading and is_unloading from loading_type"""
        for record in self:
            if record.loading_type:
                record.is_unload = "unload" in record.loading_type
                record.is_backload = "backload" in record.loading_type

    @api.constrains("unloading_start_date", "unloading_end_date")
    def _check_unloading_dates(self):
        msg = _("Unloading start time cannot be greater than end time")
        validate_dates(self.unloading_start_date, self.unloading_end_date, msg)

    @api.constrains("loading_type", "backload_ids")
    def _check_backload_ids(self):
        if self.is_backload and not self.backload_ids:
            raise ValidationError(_("Please add backloads."))

    @api.model
    def create(self, values):
        res = super(StockPickingExtras, self).create(values)
        return res
