from odoo import models, fields


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    u_last_reserved_pallet_name = fields.Char(
        string="Last Pallet Used",
        index=True,
        help="Barcode of the last pallet used for this batch. "
             "If the batch is in progress, indicates the pallet currently in "
             "use.",
    )

    def is_valid_location_dest_id(self, location_ref):
        """
        Whether the specified location is a valid putaway location
        for the relevant pickings of the batch. Expects a singleton instance.

        Parameters
        ----------
        location_ref: char
            Location identifier can be the ID, name or the barcode

        Returns a boolean indicating the validity check outcome.
        """
        self.ensure_one()
        Location = self.env["stock.location"]

        try:
            location = Location.get_location(location_ref)
        except Exception:
            return False

        done_pickings = self.picking_ids.filtered(lambda p: p.state == "assigned")
        done_move_lines = done_pickings.get_move_lines_done()
        all_done_pickings = done_move_lines.picking_id

        return all(
            [pick.is_valid_location_dest_id(location=location) for pick in all_done_pickings]
        )
