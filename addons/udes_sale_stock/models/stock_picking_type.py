from odoo import models, fields
from ..registry.suggest_by_customer import ByCustomer
from odoo.addons.udes_suggest_location.registry.suggest_locations_policy import get_selection


SUGGEST_BY_CUSTOMER = get_selection(ByCustomer)


class PickingType(models.Model):

    _inherit = "stock.picking.type"

    # Adding suggest by customer on suggest locations policy options
    u_suggest_locations_policy = fields.Selection(selection_add=[SUGGEST_BY_CUSTOMER])
