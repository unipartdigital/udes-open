from .quant_policy import QuantPolicy
from odoo import _
from odoo.exceptions import ValidationError


class QuantPolicyOneLotOrProductPerPackage(QuantPolicy):

    @classmethod
    def name(cls):
        """Set code name of the quant policy."""
        return "single_lot_id_single_product_id_per_package"

    @classmethod
    def description(cls):
        """Set description of the quant policy."""
        return "One lot/product per package"

    def apply_location_quant_policy(self, location):
        msg = "Packages %s in this location %s cannot contain more than one lot or product"
        for package, quants in location.quant_ids.groupby("package_id"):
            if len(quants.lot_id) > 1 or len(quants.product_id) > 1:
                raise ValidationError(_(msg) % (package.name, location.name))
