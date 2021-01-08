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
        """
        Set supplier from picking on backload record if:

            * It is the first backload record
            * It is a new backload record and the supplier value hasn't already been modified
            * Picking supplier has been set
        """
        # Check if field specific context has been set from form view.
        # This can be used to determine if the supplier value has been 
        # modified by the user on a new backload record.
        field_context_set = "default_supplier" in self._context

        # Backload record is the first record if the picking does not have other backload records
        is_first_record = not self._context.get("u_backload_added", False)

        if is_first_record and not self._origin and not self.supplier_id and not field_context_set:
            self.supplier_id = self._context.get("picking_supplier_id", False)

    @api.constrains("start_date", "end_date")
    def _check_backload_dates(self):
        msg = _("Backloading start time cannot be greater than end time")
        validate_dates(self.start_date, self.end_date, msg)
