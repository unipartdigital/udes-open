from odoo import api, models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def get_empty_location_domain(self):
        """
        Expand empty location domain from udes_stock to include non-blocked locations
        """
        domain = super().get_empty_location_domain()
        domain.append(("u_blocked", "=", False))
        return domain

    @api.constrains("location_id", "location_dest_id")
    def _check_locations_not_blocked(self):
        """
        Check if any of the source or destination locations are blocked
        """
        self.location_id.check_blocked(prefix=_("Wrong source location creating transfer."))
        self.location_dest_id.check_blocked(
            prefix=_("Wrong destination location creating transfer.")
        )
