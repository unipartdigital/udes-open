from odoo import models, api
from odoo.exceptions import ValidationError
from .stock_rule import RULE_RESERVATION_TYPE_WHOLE_PALLET
import logging

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _gather_whole_pallets(self, quants):
        """
        Filter quants to only include full pallets/packages which can fulfill the qty from context.
        """
        StockQuant = self.env["stock.quant"]
        filtered_quants = StockQuant.browse()
        split_pick_qty = self._context.get("split_pick_qty", 0)
        # Serialised products could be multiple quants for the same package.
        seen_packages = self.env["stock.quant.package"].browse()
        for quant in quants:
            package = quant.package_id
            # Skip any seen packages.
            if package in seen_packages:
                continue
            seen_packages |= package
            package_quants = quants.filtered(lambda q: q.package_id == package)
            if package_quants != package.quant_ids:
                _logger.warning(
                    "Possible mixed package (%s) are not supported for whole pallet reservation strategies."
                    % package.name
                )
                continue
            # Only consider the quants if their whole pallet can be reserved
            # without over-fulfilling the qty needed.
            sum_available = sum(package_quants.mapped("available_quantity"))
            sum_qty = sum(package_quants.mapped("quantity"))
            # This pallet is part reserved somehow already.
            # Maybe manual moves? Log it and skip it, we can't use it here.
            if sum_available and sum_available != sum_qty:
                _logger.warning(
                    "Whole pallet reservation attempted on pallet %s but it was skipped as pallet is already partially reserved somewhere.",
                    package.name,
                )
                continue
            if not sum_available:
                _logger.debug(
                    "Whole pallet reservation attempted on pallet %s but it was skipped as pallet is fully reserved somewhere.",
                    package.name,
                )
                continue
            if sum_qty <= split_pick_qty and package:
                filtered_quants |= quant
                split_pick_qty -= sum_qty
        return filtered_quants

    def _gather(self, product_id, location_id, **kwargs):
        """
        Extend _gather to filter by split pick rules, which were passed in via context.
        """
        split_pick_rule = self._context.get("split_pick_rule")
        filter_quants_by_rules = self._context.get("filter_quants_by_rules")

        if split_pick_rule is not None and filter_quants_by_rules:
            # If we have a rule for split pick, use its location
            # in place of the original location for quant gathering.
            location_id = split_pick_rule.location_src_id

        quants = super()._gather(product_id, location_id, **kwargs)

        # Again, need to check if we have a split pick rule in play. If so, take different reservation strategies
        # and filter quants based on those strategies.
        # For instance, if whole pallet is selected, we can only provide quants which will fully cover split_pick_qty
        # (which is effectively the qty remaining to fulfill across all strategies)
        if split_pick_rule and filter_quants_by_rules:
            reservation_type = split_pick_rule.u_run_on_assign_reservation_type
            if reservation_type == RULE_RESERVATION_TYPE_WHOLE_PALLET:
                filtered_quants = self._gather_whole_pallets(quants)
                # Our job is done. If there are other rules with different reservation types
                # then they will be managed by the parent caller (stock.move _action_assign())
                return filtered_quants

            elif not reservation_type:
                # There is no reservation type so we are allowed to just reserve
                # whatever is in the rules source location
                return quants
        return quants
