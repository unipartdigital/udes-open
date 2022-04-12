from collections import defaultdict
from datetime import datetime
import logging

from odoo import models, fields, api, _
from odoo.tools.float_utils import float_compare, float_round
from odoo.osv import expression
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _determine_priority_skipped_moveline(
        self, skipped_product_ids=None, skipped_move_line_ids=None
    ):
        """Returns a priority move line based on the first move line found
        that matches either the skipped product ids or skipped move_line_ids.
        """
        if not self:
            return False

        priority_mls = False
        # Provided skipped lists are ordered, first matching move line will have priority
        if skipped_product_ids:
            for skipped_prod_id in skipped_product_ids:
                priority_mls = self.filtered(lambda ml: ml.product_id.id == skipped_prod_id)
                if priority_mls:
                    break
        if skipped_move_line_ids:
            for skipped_ml in skipped_move_line_ids:
                priority_mls = self.filtered(lambda ml: ml.id == skipped_ml)
                if priority_mls:
                    break
        # Check if we found a priority move lines
        if priority_mls:
            return priority_mls[0]
        else:
            return False

    def _prepare_task_info(self):
        """
        Prepares info of a task.
        Assumes that all the move lines of the record set are related
        to the same picking.
        """
        self.picking_id.ensure_one()
        picking = self.picking_id
        task = {
            "picking_id": picking.id,
        }

        # Check if user_scans is manually set in context first
        user_scans = self.env.context.get("user_scans")

        if not user_scans:
            user_scans = picking.picking_type_id.u_user_scans

        if user_scans == "product":
            task["type"] = "product"
            task["pick_quantity"] = sum(self.mapped("product_qty"))
            task["quant_ids"] = self.get_quants().get_info()
        else:
            package = self.package_id
            package.ensure_one()
            info = package.get_info(extra_fields={"location_id", "quant_ids"})

            if not info:
                raise ValidationError(
                    _(
                        "Expecting package information for next task to pick,"
                        " but move line does not contain it. Contact team"
                        "leader and check picking %s"
                    )
                    % picking.name
                )

            task["type"] = "package"
            task["package_id"] = info[0]

        return task
