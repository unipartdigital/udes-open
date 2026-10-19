from .quant_policy import QuantPolicy
from odoo import _
from odoo.exceptions import ValidationError


class QuantPolicySingleProduct(QuantPolicy):

    @classmethod
    def name(cls):
        """Set code name of the quant policy."""
        return "single_product_id"

    @classmethod
    def description(cls):
        """Set description of the quant policy."""
        return "One product per location"

    def apply_location_quant_policy(self, location):
        if len(location.quant_ids.product_id) > 1:
            raise ValidationError(
                _("Location %s cannot contain more than one product." % location.name)
            )
