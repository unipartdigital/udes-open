from collections import defaultdict

from odoo import models, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _should_reserve_full_packages(self):
        """Method to determine if picking should reserve entire packages"""
        self.picking_type_id.ensure_one()
        return self.picking_type_id.u_reserve_as_packages

    def _reserve_full_packages(self):
        """
        If the picking type of the pickings in self has full package
        reservation enabled, whole packages will be reserved.
        """

        # do not reserve full packages when bypass_reserve_full packages
        # is set in the context as True
        if not self.env.context.get("bypass_reserve_full_packages"):
            pickings = self.filtered(lambda p: p._should_reserve_full_packages())
            pickings.move_line_ids.package_id

            for picking in pickings:
                remaining_qtys = defaultdict(int)

                # get all packages
                packages = picking.move_line_ids.package_id
                for package in packages:
                    move_lines = picking.move_line_ids.filtered(lambda ml: ml.package_id == package)
                    pack_products = frozenset(package._get_all_products_quantities().items())
                    mls_products = frozenset(move_lines._get_all_products_quantities().items())
                    if pack_products != mls_products:
                        # move_lines do not match the quants
                        pack_mls = package._get_current_move_lines()
                        other_pickings = pack_mls.picking_id - picking
                        if other_pickings:
                            raise ValidationError(
                                _("The package is reserved in other pickings: %s")
                                % ",".join(other_pickings.mapped("name"))
                            )

                        quants = package._get_contained_quants()
                        for product, qty in quants.get_quantities_by_key(
                            only_available=True
                        ).items():
                            remaining_qtys[product] += qty
                if remaining_qtys:

                    products_info = []
                    for product, qty in remaining_qtys.items():
                        products_info.append({"product": product, "uom_qty": qty})

                    # TODO: Issue 962, may need to adjust for it to work with different UoMs

                    move_values = self._prepare_move(
                        picking, [products_info], u_uom_initial_demand=0
                    )

                    picking._create_move(move_values)

                    # add bypass_zero_qty_log_message context to avoid temporary moves being logged
                    picking.with_context(bypass_zero_qty_log_message=True).action_confirm()

                    # add bypass_reserve_full_packages at the context
                    # to avoid to be called again inside _create_move()
                    picking.with_context(bypass_reserve_full_packages=True).action_assign()
