"""
Package model: advanced features.

The term package has two meanings:
- a generic container, either a package or a package
- a container containing only quants

A pallet is a containers which contains only quants.

A container may not contain a mix of packages and quants.
"""
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
        Package = self.env["stock.quant.package"]
        User = self.env["res.users"]

        warehouse = User.get_user_warehouse()
        self.ensure_one()
        # Prevent renaming pallet to package if pallet contains packages.
        if Package.search_count([("parent_id", "=", self.id)]) > 0:
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
            raise ValidationError(_(f"Invalid {type_} name %r." % self.name))

    def validate_parent_name(self, vals):
        """Raise an exception for parent names that don't match the pallet barcode regex."""
        Package = self.env["stock.quant.package"]
        User = self.env["res.users"]

        # The desktop package creation UI will pass `False` for the parent
        # field if it isn't populated.
        if "parent_id" in vals and vals["parent_id"]:
            warehouse = User.get_user_warehouse()
            pattern = warehouse.u_pallet_barcode_regex
            pallet = Package.browse(vals["parent_id"])
            if not re.match(pattern, pallet.name):
                _logger.debug("Pallet name %r does not match pattern %r", pallet.name, pattern)
                raise ValidationError(_("Invalid pallet name %r.") % pallet.name)
        return

    @api.constrains("children_ids")
    def _check_child_names(self):
        """
        Raise an exception for invalid configurations.

        The parent's name must match the pallet regex.
        Children's names must match the package regex.
        """
        User = self.env["res.users"]

        self.ensure_one()

        warehouse = User.get_user_warehouse()
        pattern = warehouse.u_package_barcode_regex
        for child in self.children_ids:
            if not re.match(pattern, child.name):
                raise ValidationError(_("Invalid package name %r") % child.name)
        return

    @api.model
    def create(self, vals):
        """
        Create a new instance of the model from vals.

        Attempts to create an instance with invalid `name`, or a parent
        which is not a pallet will raise an exception.
        """
        self.validate_parent_name(vals)
        return super().create(vals)

    def write(self, vals):
        """
        Update a recordset with vals.

        Attempts to update an instance with an invalid `name`, or a parent
        which is not a pallet will raise an exception.
        """
        self.validate_parent_name(vals)
        return super().write(vals)
