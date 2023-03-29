from odoo import models, fields
from ..registry.suggest_by_product import ByProduct
from ..registry.suggest_by_empty_location import ByEmptyLocation
from ..registry.suggest_exactly_match_move_line import ExactlyMatchMoveLine
from ..registry.suggest_by_origin import ByOrigin
from ..registry.suggest_locations_policy import get_selection


SUGGEST_LOCATION_POLICIES = [
    get_selection(ExactlyMatchMoveLine),
    get_selection(ByProduct),
    get_selection(ByEmptyLocation),
    get_selection(ByOrigin),
]


class PickingType(models.Model):

    _inherit = "stock.picking.type"

    # The policy is fetched on implementation
    u_suggest_locations_policy = fields.Selection(
        selection=SUGGEST_LOCATION_POLICIES,
        string="Suggest locations policy",
        help="The policy used to suggest locations",
        default=ExactlyMatchMoveLine.name(),
    )

    # We could move the definition somewhere else and extend to add suggestion
    # based constraints
    u_drop_location_constraint = fields.Selection(
        [
            ("dont_scan", "Do not scan"),
            ("scan", "Scan"),
            ("suggest", "Suggest"),
            ("suggest_with_empty", "Suggest with empty locations"),
            ("enforce", "Enforce"),
            ("enforce_with_empty", "Enforce with empty locations"),
        ],
        default="scan",
        string="Suggest locations constraint",
        help="Whether drop locations should be scanned, suggested and, then, enforced.",
    )
