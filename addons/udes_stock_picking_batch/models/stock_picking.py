from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def get_move_lines_done(self):
        """ Return the recordset of move lines done. """
        return self.move_line_ids.filtered(lambda o: o.qty_done > 0)

    def is_valid_location_dest_id(self, location=None, location_ref=None):
        """Whether the specified location or location reference is a valid
        putaway location for the picking. Expects a singleton instance.

        Parameters
        ----------
        location : Location obj
            Location record
        location_ref: char
            Location identifier can be the ID, name or the barcode

        Returns a boolean indicating the validity check outcome.
        """
        Location = self.env["stock.location"]
        self.ensure_one()

        if not location and not location_ref:
            raise ValidationError("Must specify a location or ref")

        dest_location = location or Location.get_location(location_ref)
        if not dest_location:
            raise ValidationError(_("The specified location is unknown."))

        valid_locations = self._get_child_dest_locations([("id", "=", dest_location.id)])

        return valid_locations.exists()
