from odoo import models, fields
from ..registry.suggest_by_customer import ByCustomer
from ..registry.suggest_by_carrier import ByCarrier
from odoo.addons.udes_suggest_location.registry.suggest_locations_policy import get_selection


SUGGEST_BY_CUSTOMER = get_selection(ByCustomer)
SUGGEST_BY_CARRIER = get_selection(ByCarrier)
SUGGEST_LOCATION_POLICIES = [
    SUGGEST_BY_CUSTOMER,
    SUGGEST_BY_CARRIER,
]


class PickingType(models.Model):

    _inherit = "stock.picking.type"

    # Adding suggest by customer/carrier on suggest locations policy options
    u_suggest_locations_policy = fields.Selection(selection_add=SUGGEST_LOCATION_POLICIES)
    u_full_sale_reservation = fields.Boolean(
        string="Full Sale Reservation",
        default=False,
        help="Flag to indicate that all picks which are created from same sale order will be reserved at same time.",
    )
