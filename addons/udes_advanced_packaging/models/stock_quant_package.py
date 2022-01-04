"""Package model: advanced features."""
import logging
import re

from odoo import api, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockQuantPackage(models.Model):
    """A package contains one or more quants or subpackages."""

    _inherit = ["stock.quant.package", "mixin.stock.model"]
    _name = "stock.quant.package"
    _sql_constraints = [("name_unique", "unique (name)", "This name has already been used")]

    @api.constrains("name")
    def _check_name(self):
        warehouse = self.env.ref("stock.warehouse0")

        self.ensure_one()
        # Prevent renaming pallet to package if pallet contains packages.
        if self.search_count([("parent_id", "=", self.id)]) > 0:
            pattern = warehouse.u_pallet_barcode_regex
            type_ = "pallet"
        else:
            # Absent any other information, we don't know if a package is a package
            # of quants or a package of packages (pallet), so the name may match
            # either.
            pattern = f"{warehouse.u_package_barcode_regex}|{warehouse.u_pallet_barcode_regex}"
            type_ = "package"
        if not re.match(pattern, self.name):
            _logger.debug("%s name %r does not match pattern %r", type_.title(), self.name, pattern)
            raise ValidationError(_(f"Invalid {type_} name {self.name!r}."))

    def _validate_pallet_name(self, vals):
        """Raise an exception for names that don't match the pallet barcode regex."""
        warehouse = self.env.ref("stock.warehouse0")

        if "parent_id" in vals:
            pallet = self.browse(vals["parent_id"])
            pattern = warehouse.u_pallet_barcode_regex
            if not re.match(pattern, pallet.name):
                _logger.debug("Pallet name %r does not match pattern %r", pallet.name, pattern)
                raise ValidationError(_(f"Invalid pallet name {pallet.name!r}."))
        return

    @api.model
    def create(self, vals):
        """Create a new instance of the model."""
        self._validate_pallet_name(vals)
        return super().create(vals)

    def write(self, vals):
        """Update the records in this recordset."""
        self._validate_pallet_name(vals)
        return super().write(vals)
