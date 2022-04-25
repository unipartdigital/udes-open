import logging

from odoo import models, _
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

    def next_task_sort(self):
        """Creating a method so we can override it by sorting another combination.
        Would be easier and meaningful than to extend sort_by_key as we may need to change the
        behaviour of next_task_sort result rather than changing the behaviour of sort_by_key"""
        return self.sort_by_key()

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
            info = package.get_info(extra_fields={"location_id", "quant_ids"}, max_level=3)

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

    def _get_next_drop_off_all(self, item_identity):
        raise ValidationError(_("The 'all' drop off criterion should not be invoked"))

    def _get_next_drop_off_by_products(self, item_identity):
        mls = self.filtered(lambda ml: ml.product_id.barcode == item_identity)
        summary = mls._drop_off_criterion_summary()

        return mls, summary

    def _get_next_drop_off_by_orders(self, item_identity):
        mls = self.filtered(lambda ml: ml.picking_id.origin == item_identity)
        summary = mls._drop_off_criterion_summary()

        return mls, summary

    def _get_next_drop_off_by_packages(self, item_identity):
        mls = self.filtered(lambda ml: ml.result_package_id.name == item_identity)
        summary = mls._drop_off_criterion_summary()

        return mls, summary

    def _drop_off_criterion_summary(self):
        """Generate product summary for drop off criterion for the move
        lines in self.
        Generate one piece of information for each product:
        * Display name
        * Total quantity in move lines
        * Speed of the product (if it is set)
        """
        summary = ""
        for product, prod_mls in self.groupby(lambda ml: ml.product_id):
            product_speed = ""
            if product.u_speed_category_id:
                product_speed = " (speed: {})".format(product.u_speed_category_id.name)
            summary += "<br>{} x {}{}".format(
                product.display_name, int(sum(prod_mls.mapped("qty_done"))), product_speed
            )
        return summary
