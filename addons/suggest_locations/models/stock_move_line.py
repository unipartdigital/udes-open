# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .suggest_locations_policy import SUGGEST_LOCATION_REGISTRY

from functools import lru_cache

DROPABLE_STATES = ("assigned", "partially_available")
CONTRAINTS_REQUIRING_A_CHECK = ("enforce", "enforce_with_empty")
VIEW_SET = set(["view"])


class MoveLine(models.Model):
    _inherit = "stock.move.line"

    u_picking_type_id = fields.Many2one(related="move_id.picking_type_id")

    @lru_cache(maxsize=10)
    def _get_policy_class(self, picking_type, preprocessing=False):
        try:
            policy_name = picking_type.u_suggest_locations_policy
            policy_class = SUGGEST_LOCATION_REGISTRY[policy_name]
            return policy_class(self.env, preprocessing)
        except KeyError:
            # TODO: better error and _
            raise ValueError("policy not found")

    def suggest_locations(
        self, picking_type=None, values=None, limit=30, preprocessing=False
    ):

        # Validate preconditions
        if not self and (not picking_type or not values):
            # TODO: better error and _
            raise ValueError("Missing infomation")

        if self and not picking_type:
            picking_type = self.mapped("u_picking_type_id")

        picking_type.ensure_one()

        if (
            not picking_type.u_suggest_locations_policy
            or picking_type.u_suggest_locations_policy == "None"
        ):
            raise ValueError("No policy set")

        # Get policy class
        policy = self._get_policy_class(picking_type, preprocessing)

        # Process values required
        if self:
            values = policy.get_values_from_mls(self)
        else:
            values = policy.get_values_from_dict(values)

        # Get locations :)
        locations = policy.get_locations(**values)

        if picking_type.u_drop_location_constraint == "enforce_with_empty":
            locations |= picking_type.default_location_dest_id.get_empty_children()

        return locations[:limit]

    @api.constrains("location_dest_id")
    @api.onchange("location_dest_id")
    def validate_location_dest(self, locations=None):
        """Check the drop location is valid"""

        # What move lines can be dropped?
        drop_mls = self.filtered(lambda ml: ml.state in DROPABLE_STATES)
        if not drop_mls:
            return

        # TODO: see if we can handle this in a nicer way
        # On create we need to allow views to pass.
        # On other actions if this will be caught by odoo's code as you are not
        # allowed to place stock in a view.
        if locations and set(locations.mapped("usage")) == VIEW_SET:
            return

        # Group mls so we can do policy dependant check
        for picking_type, mls in drop_mls.groupby("u_picking_type_id"):

            if not picking_type.u_suggest_locations_policy:
                pass

            # Do we even need to check?
            constraint = picking_type.u_drop_location_constraint
            if constraint not in CONTRAINTS_REQUIRING_A_CHECK:
                continue

            policy = self._get_policy_class(picking_type)

            for mls_validation_grp in policy.iter_mls(mls):

                # Get the suggested locations for comparison
                suggested_locations = mls_validation_grp.suggest_locations()

                if not suggested_locations:
                    continue

                # If no location was passed, get the ones from the move lines
                locs = locations
                if not locs:
                    locs = mls_validation_grp.mapped("location_dest_id")

                # locs should be one of the suggested locations
                if locs not in suggested_locations:
                    raise ValidationError(
                        _("Drop off location must be one of the suggested locations")
                    )
