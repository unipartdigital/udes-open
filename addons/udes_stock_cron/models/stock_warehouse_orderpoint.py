from odoo import models, api, _, registry
from odoo.exceptions import UserError
from odoo.addons.stock.models.stock_rule import ProcurementException
from odoo.tools import float_compare, format_date
from datetime import datetime, time
from psycopg2 import OperationalError

import logging

_logger = logging.getLogger(__name__)


class StockWarehouseOrderPoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    PREFETCH_MAX = 1000

    @api.model
    def check_order_points(
        self,
        use_new_cursor=False,
        company_id=False,
        location_id=False,
        excluded_location_ids=False,
    ):
        """
        Extend this method to include raise_user_error in context to make sure we can skip
        faulty procurement and raise an error after all valid procurements are done.
        As cron running automatically and manually have different context
        """
        self = self.with_context(raise_user_error=False)
        res = super().check_order_points(
            use_new_cursor=use_new_cursor,
            company_id=company_id,
            location_id=location_id,
            excluded_location_ids=excluded_location_ids,
        )

        return res

    def _procure_orderpoint_confirm(
        self, use_new_cursor=False, company_id=None, raise_user_error=True
    ):
        """Create procurements based on orderpoints.
        Copy of base method with needed customization.
        With cron skip faulty procurements instead of raising errors.
        Combine errors and raise after finishing non-faulty procurements.
        Post message on products instead of creating planned activities.
        Use batched() for making batches.
        :param bool use_new_cursor: if set, use a dedicated cursor and auto-commit after processing
            PREFETCH_MAX orderpoints.
            This is appropriate for batch jobs only.
        """
        self = self.with_company(company_id)
        ctx = self._context
        # set raise_user_error to false if method call is from cron
        # this allows us to skip faulty procurements and avoid raising errors
        raise_user_error = ctx.get("raise_user_error")
        all_skipped_errors = ""
        for _range, orderpoints_batch in self.batched(self.PREFETCH_MAX):
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))
            orderpoints_exceptions = []
            orderpoints_batch = self.env["stock.warehouse.orderpoint"].browse(
                orderpoints_batch.ids
            )
            while orderpoints_batch:
                procurements = []
                for orderpoint in orderpoints_batch:
                    if (
                        float_compare(
                            orderpoint.qty_to_order,
                            0.0,
                            precision_rounding=orderpoint.product_uom.rounding,
                        )
                        == 1
                    ):
                        date = datetime.combine(orderpoint.lead_days_date, time.min)
                        values = orderpoint._prepare_procurement_values(date=date)
                        procurements.append(
                            self.env["procurement.group"].Procurement(
                                orderpoint.product_id,
                                orderpoint.qty_to_order,
                                orderpoint.product_uom,
                                orderpoint.location_id,
                                orderpoint.name,
                                orderpoint.name,
                                orderpoint.company_id,
                                values,
                            )
                        )

                try:
                    with self.env.cr.savepoint():
                        self.env["procurement.group"].with_context(
                            from_orderpoint=True
                        ).run(procurements, raise_user_error=raise_user_error)
                except ProcurementException as errors:
                    for procurement, error_msg in errors.procurement_exceptions:
                        orderpoints_exceptions += [
                            (procurement.values.get("orderpoint_id"), error_msg)
                        ]
                    failed_orderpoints = self.env["stock.warehouse.orderpoint"].concat(
                        *[o[0] for o in orderpoints_exceptions]
                    )
                    if not failed_orderpoints:
                        _logger.error("Unable to process orderpoints")
                        break
                    orderpoints_batch -= failed_orderpoints

                except OperationalError:
                    if use_new_cursor:
                        cr.rollback()
                        continue
                    else:
                        raise
                else:
                    orderpoints_batch._post_process_scheduler()
                    break

            # Log a message on product template for failed orderpoints
            # concat skipped errors in variable all_skipped_errors
            for orderpoint, error_msg in orderpoints_exceptions:
                all_skipped_errors += "->" + error_msg + "\n"
                op_product = orderpoint.product_id.product_tmpl_id
                exception_msg = "Exception: " + error_msg
                op_product.message_post(body=_(exception_msg))

            if use_new_cursor:
                cr.commit()
                cr.close()

        # after finishing all valid not faulty procurements raise all_skipped_errors as an UserError
        # this should set cron to failed state and log errors in failures tab
        # if raise_user_error is true that means we are already raising errors and stopping execution
        # in this case we do not need to raise error separately.
        if all_skipped_errors and not raise_user_error:
            raise UserError(_(all_skipped_errors))
        return {}
