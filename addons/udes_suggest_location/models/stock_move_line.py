# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import ValidationError
from ..registry.suggest_locations_policy import SUGGEST_LOCATION_REGISTRY

NON_DROPABLE_STATES = ("cancel", "draft", "done")
CONSTRAINTS_REQUIRING_A_CHECK = ("enforce", "enforce_with_empty")
WITH_EMPTY_LOCATIONS = ("suggest_with_empty", "enforce_with_empty")
VIEW_SET = set(["view"])


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_policy_class(self, picking_type):
        """Get the policy for suggesting locations
        Note: Optionally we could cache the results with @lru_cache to avoid always returning the
        policy class, but this caused issued with closed cursors. To avoid this,
        you need to update the environment at the same time you return the cached result.
        Possibly by having another function that returns the cached class and updated environment
        by policy.env = self.env
        """
        try:
            policy_type = picking_type.u_suggest_locations_policy
            policy_class = SUGGEST_LOCATION_REGISTRY[policy_type]
            return policy_class(self.env)
        except KeyError:
            raise ValueError(_("Policy with name=%s could not be found") % policy_type)

    def suggest_locations(self, picking=None, values=None, limit=30):
        """
        Suggest locations for move line, either by self or picking_type and values

        - picking: {stock.picking}
            If not set, it will be determined from the picking for the stock move line in self
        - values: Dictionary
            Used to determine values to use when self is an empty recordset
        - limit: Integer
            If set then the location recordset returned will be less than or equal to the limit.
        """
        # Validate preconditions
        if not self and (not picking or not values):
            raise ValueError(
                _(
                    "Missing information to suggest locations, please provide either move "
                    + "lines or picking and values!"
                )
            )
        # Set the picking
        if self and not picking:
            picking = self.picking_id

        picking_type = picking.picking_type_id

        picking_type.ensure_one()
        policy_type = picking_type.u_suggest_locations_policy
        if not policy_type or policy_type == "None":
            raise ValueError(_("No policy set"))

        # Get policy class
        policy = self._get_policy_class(picking_type)
        # Process values required
        if self:
            values = policy.get_values_from_mls(self)
        else:
            values = policy.get_values_from_dict(values)
        # Get locations
        locations = policy.get_locations(**values)

        if picking_type.u_drop_location_constraint in WITH_EMPTY_LOCATIONS:
            empty_locations_limit = None
            if limit:
                # Only get the number of empty locations needed to reach the limit
                location_count = len(locations.ids)
                empty_locations_limit = limit - location_count

            if empty_locations_limit is None or empty_locations_limit > 0:
                locations |= picking.get_empty_locations(limit=empty_locations_limit)

        if limit:
            locations = locations[:limit]

        return locations

    @api.constrains("location_dest_id")
    @api.onchange("location_dest_id")
    def validate_location_dest(self, locations=None):
        """Check the drop location is valid"""

        # What move lines can be dropped?
        # We use the double negative as sometimes we need to check the destination location before
        # they become assigned
        drop_mls = self.filtered(lambda ml: ml.state not in NON_DROPABLE_STATES)
        if not drop_mls:
            return
        # On create we allow views to pass, we rely on core odoo to block
        # stock being dropped in a view location.
        if locations and set(locations.mapped("usage")) == VIEW_SET:
            return
        # Group mls so we can do policy dependant check
        for picking_type, mls in drop_mls.groupby("u_picking_type_id"):
            if not picking_type.u_suggest_locations_policy:
                continue

            constraint = picking_type.u_drop_location_constraint
            if constraint not in CONSTRAINTS_REQUIRING_A_CHECK:
                continue

            # Get policy
            policy = self._get_policy_class(picking_type)

            for mls_validation_grp in policy.iter_mls(mls):
                # If no location was passed, get the ones from the move lines
                locs = locations or mls_validation_grp.location_dest_id
                if set(locs.mapped("usage")) == VIEW_SET:
                    # Allow view destination locations on create
                    continue
                # Get the suggested locations for comparison
                suggested_locations = mls_validation_grp.suggest_locations()
                if not suggested_locations:
                    raise ValidationError(_("There are no valid locations to drop stock"))

                # locs should be one of the suggested locations
                if locs not in suggested_locations:
                    raise ValidationError(
                        _("Drop off location must be one of the suggested locations")
                    )
