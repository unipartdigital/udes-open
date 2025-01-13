from odoo.addons.udes_suggest_location.registry.suggest_locations_policy import SuggestLocationPolicy
from odoo.tools.translate import _


class ByCustomer(SuggestLocationPolicy):
    """Find locations based on other quants for the same customer"""

    @classmethod
    def name(cls):
        return "by_customer"

    def get_values_from_mls(self, mls):
        """
        Get the suggested location destination of the move line from move lines
        """
        return {
            "customer": mls.move_id.sale_line_id.order_id.partner_id.ensure_one(),
            "location": mls.picking_id.location_dest_id.ensure_one(),
        }

    def _get_picking_from_dict(self, values):
        """Get the picking from the values, assumed to be the int id of a picking"""
        Picking = self.env["stock.picking"]
        picking_id = values.get("picking_id")
        if not picking_id:
            raise ValueError(_("No picking found"))
        return Picking.browse(picking_id)

    def get_values_from_dict(self, values):
        """
        Get the suggested location destination of the move line from values
        """
        picking = self._get_picking_from_dict(values)
        customer = picking.move_id.sale_line_id.order_id.partner_id
        return {
            "customer": customer,
            "location": picking.location_dest_id,
        }

    def get_locations(self, customer, location, **kwargs):
        """
        Return stock.locations whose current quants are derived from a sales order
        for the same customer as the one passed in.
        If no match is found, return emptyset of stock.location.
        Adding empty locations to this is handled by the caller of this function.
        """
        StockMoveLine = self.env["stock.move.line"]
        # Find all 'Ready' moves to be moved from the destination location
        # Note that, this wouldn't work if 'by customer' is configured on the last
        # picking in a chain, as there will be no followup moves. This shouldn't
        # matter as the quants are just going out of the warehouse in that case.
        move_lines = StockMoveLine.search([
            ("state", "=", "assigned"),
            ("location_id", "child_of", location.id)
        ])
        return move_lines.filtered(
            lambda ml: ml.move_id.sale_line_id.order_id.partner_id == customer
        ).location_id  # Can be singleton, multi, or emptyset!


    def iter_mls(self, mls):
        for _customer, grouped_mls in mls.groupby(
                lambda ml: ml.move_id.sale_line_id.order_id.partner_id
        ):
            yield grouped_mls
