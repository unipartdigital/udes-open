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
        Do some simple checks on the location.
        """
        location.ensure_one() 

        # TODO: In UDES11 also filters by u_blocked, can add when u_blocked is ported. 
        if location.usage == "view": 
            location = self.env["stock.location"]

        return location 

    def iter_mls(self, mls):
        """
        Group by the moveline location destination
        """
        for _prod, grouped_mls in mls.groupby("location_dest_id"):
            yield grouped_mls