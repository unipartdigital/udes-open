from odoo.exceptions import ValidationError
from .suggest_locations_policy import SuggestLocationPolicy
from odoo.tools.translate import _


class ExactlyMatchMoveLine(SuggestLocationPolicy):
    """Exactly match the move line"""

    @classmethod
    def name(cls):
        return "exactly_match_move_line"

    def get_values_from_mls(self, mls):
        """
        Get the suggested location destination of the move line from values
        """
        return {
            "location": mls.location_dest_id.ensure_one(),
        }

    def _get_location_dest_from_dict(self, values):
        Location = self.env["stock.location"]
        location_dest_id = values.get("location_dest_id")
        if not location_dest_id:
            raise ValueError(_("No destination location found"))
        return Location.browse(location_dest_id)

    def get_values_from_dict(self, values):
        """
        Get the suggested location destinaton of the move line from values
        """
        location = self._get_location_dest_from_dict(values)
        return {
            "location": location,
        }

    def get_locations(self, location, **kwargs):
        """
        Check the location is not of type view, and that there is only one location.
        """
        StockLocation = self.env["stock.location"]
        location.ensure_one()

        if location.usage == "view":
            return StockLocation.browse()
        return location

    def iter_mls(self, mls):
        """
        Group by the moveline location destination
        """
        for _location_dest_id, grouped_mls in mls.groupby("location_dest_id"):
            yield grouped_mls
