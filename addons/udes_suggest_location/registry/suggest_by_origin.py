"""By Origin policy implementation."""
from .suggest_locations_policy import SuggestLocationPolicy


class ByOrigin(SuggestLocationPolicy):
    """Find locations based on the origin of moves."""

    @classmethod
    def name(cls):
        """Return the policy's name."""
        return "by_origin"

    def get_values_from_mls(self, mls):
        """Extract location and origin from move lines."""
        origins = set(mls.mapped("picking_id.origin"))
        if len(origins) != 1:
            raise ValueError(f"Expected single origin, got: {sorted(origins)}")
        origin = origins.pop()
        return {
            "location": mls.picking_id.location_dest_id.ensure_one(),
            "origin": origin,
        }

    def get_values_from_dict(self, values):
        """Extract location and origin from the provided dictionary."""
        Picking = self.env["stock.picking"]

        picking = Picking.browse(values["picking_id"])
        return {
            "location": picking.location_dest_id,
            "origin": picking.origin,
        }

    def get_locations(self, origin, location, **kwargs):
        """Get all locations that are the location or its child with the same origin."""
        MoveLine = self.env["stock.move.line"]
        mls_for_location = MoveLine.search(
            [
                ("picking_id.state", "=", "done"),
                ("picking_id.origin", "=", origin),
                ("location_dest_id", "child_of", location.id),
            ],
            order="id",
        )
        return mls_for_location.location_dest_id

    def iter_mls(self, mls):
        """Iterate over move lines grouped by origin."""
        for _origin, grouped_mls in mls.groupby(lambda ml: ml.picking_id.origin):
            yield grouped_mls
