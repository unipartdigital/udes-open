"""
Package model: additional features.

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

    @api.constrains("child_ids")
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
        for child in self.child_ids:
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

    def _get_all_products_quantities(self):
        """This function computes the different product quantities for the given package"""
        # TODO: Issue 962, make this work with different UoMs
        res = {}
        for quant in self._get_contained_quants():
            if quant.product_id not in res:
                res[quant.product_id] = 0
            res[quant.product_id] += quant.quantity
        return res

    def assert_reserved_full_package(self, move_lines):
        """Check that a package is fully reserved at move_lines."""
        self.ensure_one()

        pack_products = frozenset(self._get_all_products_quantities().items())
        mls_products = frozenset(move_lines._get_all_products_quantities().items())
        if pack_products != mls_products:
            # move_lines do not match the quants
            picking = move_lines.picking_id
            picking.ensure_one()
            pack_mls = self._get_current_move_lines()
            other_pickings = pack_mls.picking_id - picking
            if other_pickings:
                raise ValidationError(
                    _("The package is reserved in other pickings: %s")
                    % ",".join(other_pickings.mapped("name"))
                )
            raise ValidationError(
                _("Cannot mark partially reserved package %s as done.") % self.name
            )

    def prepare_result_packages(
        self,
        product_ids,
        package,
        result_package_name,
        result_parent_package_name,
        target_storage_format,
        scan_parent_package_end,
    ):
        """
        Compute result_package and result_parent_package based on the target_storage_format supplied
        and the input parameters.
        """
        Package = self.env["stock.quant.package"]

        result_package = None
        result_parent_package = None

        if target_storage_format == "pallet_packages":

            # CASE A: both package names given
            if result_package_name and result_parent_package_name:
                result_package = Package.get_or_create(result_package_name, create=True)
                result_parent_package = Package.get_or_create(
                    result_parent_package_name, create=True
                )
            # CASE B: only one of the package names is given as result_package
            elif result_package_name or scan_parent_package_end:
                # At pallet_packages, result_package parameter is expected
                # to be the result_parent_package of the move_line
                # It might be a new pallet id
                if not scan_parent_package_end:
                    result_parent_package = Package.get_or_create(result_package_name, create=True)
                # MPS: maybe this if is not needed
                if not package:
                    if product_ids:
                        # Products are being packed
                        result_package = Package.create({})
                    elif not all([ml.result_package_id for ml in self]):
                        # Setting result_parent_package expects to have
                        # result_package for all the move lines
                        raise ValidationError(
                            _("Some of the move lines don't have result package.")
                        )
                    else:
                        # We don't have either package or products and all lines have
                        # result_package_id so parent_package should be result package parameter
                        result_parent_package = Package.get_or_create(
                            result_package_name, create=True
                        )
                        result_package = None
                else:
                    # Products are being packed into a new package
                    result_package = None
                    if product_ids:
                        result_package = Package.create({})
            # CASE C: wrong combination of package names given
            elif product_ids:
                raise ValidationError(
                    _("Invalid parameters for target storage format, expecting result package.")
                )

        elif target_storage_format == "pallet_products":
            if result_package_name:
                # Moving stock into a pallet of products, result_package
                # might be new pallet id
                result_package = Package.get_or_create(result_package_name, create=True)
            elif product_ids and not result_package_name and not scan_parent_package_end:
                raise ValidationError(
                    _("Invalid parameters for target storage format, expecting result package.")
                )

        elif target_storage_format == "package":
            if product_ids and not package and not result_package_name:
                # Mark_as_done products without package or result_package
                # Create result_package when packing products without
                # result_package being set
                result_package = Package.create({})

        elif target_storage_format == "product":
            # Error when trying to mark_as_done a full package or setting result package
            # when result storage format is products
            if result_package_name:
                raise ValidationError(_("Invalid parameters for products target storage format."))

        return result_package, result_parent_package
