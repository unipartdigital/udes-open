from odoo import api, fields, models, _
from ..misc import date_diff, validate_dates


class StockPickingBackload(models.Model):
    """
        Stock picking backload to hold all backload related values
    """

    _name = "stock.picking.backload"
    _description = "UDES Stock Picking Backload"

    extras_id = fields.Many2one("stock.picking.extras")

    # Back Loading Fields
    supplier_id = fields.Many2one(
        "res.partner",
        "Supplier",
        domain="[('supplier', '=', True)]",
        help="Supplier from the backload",
    )
    pallet_count = fields.Integer(help="Number of pallets backloaded", default=0)
    stillage_count = fields.Integer(help="Number of stillages backloaded", default=0)
    box_count = fields.Integer(help="Number of boxes backloaded", default=0)
    cover_count = fields.Integer(help="Number of covers backloaded", default=0)
    reject_count = fields.Integer(
        help="Number of pallets/stillages/covers rejected and not backloaded", default=0
    )
    start_date = fields.Datetime("Start Date/Time", help="Backload Start Date/Time")
    end_date = fields.Datetime("End Date/Time", help="Backload End Date/time")
    time_taken = fields.Float(
        "Backloading Time HH:MM",
        compute="_compute_time_taken",
        store=True,
        readonly=True,
        help="The amount of time taken to complete backloading in HH:MM format",
    )

    @api.multi
    @api.depends("start_date", "end_date")
    def _compute_time_taken(self):
        """ Compute time_taken field """
        for record in self:
            record.time_taken = 0
            if record.start_date and record.end_date:
                record.time_taken = date_diff(record.start_date, record.end_date)

    @api.onchange("supplier_id")
    def _onchange_supplier_id(self):
        supplier_id = self._context.get("supplier", False)
        if not self.supplier_id and supplier_id:
            self.supplier_id = supplier_id

    @api.constrains("start_date", "end_date")
    def _check_backload_dates(self):
        msg = _("Backloading start time cannot be greater than end time")
        validate_dates(self.start_date, self.end_date, msg)
