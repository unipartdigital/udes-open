from .suggest_locations_policy import SuggestLocationPolicy
from odoo.tools.translate import _


class ByEmptyLocation(SuggestLocationPolicy):
    """Find empty locations of the picking destination location"""

    @classmethod
    def name(cls):
        return "by_empty_location"

    def get_values_from_mls(self, mls):
        """
        Get the picking destination location from the move lines
        """
        return {
            "location": mls.picking_id.location_dest_id.ensure_one(),
        }

    def _get_picking_from_dict(self, values):
        Picking = self.env["stock.picking"]
        picking_id = values.get("picking_id")
        if not picking_id:
            raise ValueError(_("No picking found"))
        return Picking.browse(picking_id)

    def get_values_from_dict(self, values):
        """
        Get the picking destination location from the values
        """
        picking = self._get_picking_from_dict(values)
        return {
            "location": picking.location_dest_id,
        }

    def get_locations(self, location, **kwargs):
        """
        Search for locations which are children of the picking destination location
        """
        Location = self.env["stock.location"]

        # Add order="id" for performance as we don't care about the order
        child_locations_of_picking_destination = Location.search(
            [
                ("location_id", "child_of", location.id),
                ("barcode", "!=", False),
                ("quant_ids", "=", False),
            ],
            order="id",
        )
        return child_locations_of_picking_destination

    def iter_mls(self, mls):
        """
        Group by picking ID as the mls depend on picking destination location
        """
        for _picking_id, grouped_mls in mls.groupby("picking_id"):
            yield grouped_mls
