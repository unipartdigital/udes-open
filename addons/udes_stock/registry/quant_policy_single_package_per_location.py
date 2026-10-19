from .quant_policy import QuantPolicy
from odoo.exceptions import ValidationError
from odoo import _


class QuantPolicyOnePackagePerLocation(QuantPolicy):

    @classmethod
    def name(cls):
        """Set code name of the quant policy."""
        return "single_package_per_location"

    @classmethod
    def description(cls):
        """Set description of the quant policy."""
        return "One package per location"

    def apply_location_quant_policy(self, location):
        if len(location.quant_ids.package_id) > 1:
            raise ValidationError(_("Location %s should only contain one package.") % location.name)
