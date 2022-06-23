# -*- coding: utf-8 -*-

from collections import defaultdict
from odoo import api, fields, models, tools, _
import logging
from datetime import timedelta, date
import time
import traceback
from odoo.addons.udes_common import exceptions

from psycopg2 import OperationalError, errorcodes

PG_CONCURRENCY_ERRORS_TO_RETRY = (
    errorcodes.LOCK_NOT_AVAILABLE,
    errorcodes.SERIALIZATION_FAILURE,
    errorcodes.DEADLOCK_DETECTED,
)

_logger = logging.getLogger(__name__)

PRIORITIES = [('0', 'Normal'), ('1', 'Urgent')]


class SaleOrder(models.Model):
    _inherit = "sale.order"
    _order = "requested_date asc, priority desc, id asc"

    # Add index to origin as this field is frequently used in searches
    origin = fields.Char(
        string="Source Document",
        help="Reference of the document that generated this sales order request.",
        index=True,
    )

    # Rename states
    state = fields.Selection(selection_add=[("sale", "In Progress"), ("done", "Done"),])

    picking_ids = fields.One2many(
        "stock.picking",
        # inverse_name=None,
        compute="_compute_picking_ids_by_line"
    )

    priority = fields.Selection(
        selection=PRIORITIES,
        inverse="_set_priority",
        default="0",
        string="Priority",
        index=True,
        states={"done": [("readonly", True)], "cancel": [("readonly", True)]},
    )

    # Set Customer Reference and Requested Date fields to be required
    # and to be copied when Order is duplicated
    client_order_ref = fields.Char(required=True, copy=True)
    requested_date = fields.Datetime(required=True, copy=True)

    u_allow_manual_sale_order_line_cancellation = fields.Boolean(
        readonly=True, related="warehouse_id.u_allow_manual_sale_order_line_cancellation",
    )

    @api.depends("order_line.move_ids.picking_id")
    def _compute_picking_ids_by_line(self):
        self.mapped("order_line.move_ids.picking_id")
        for order in self:
            order.picking_ids = order.mapped("order_line.move_ids.picking_id")

    def copy(self, default=None):
        """Append '(copy)' to Customer Reference for duplicated Order if not supplied"""
        if not dict(default or {}).get('client_order_ref'):
            default = dict(default or {}, client_order_ref=_("%s (copy)") % self.client_order_ref)
        return super(SaleOrder, self).copy(default)

    def _set_priority(self):
        for order in self:
            order.mapped("order_line.move_ids").write({"priority": order.priority})

    @api.model
    def cancel_orders_without_availability(self, aux_domain=None):
        """From the current list of unconfirmed SO lines, cancel lines that
        cannot be fulfilled with current stock holding and returns them"""
        Order = self.env["sale.order"]
        domain = [("state", "in", ["sale", "draft"])]

        # Get order lines
        if aux_domain is not None:
            domain += aux_domain
        orders = Order.search(domain)
        unfulfillable_lines = orders._find_unfulfillable_order_lines()

        _logger.info("Cancelling %s unfulfillable order lines", len(unfulfillable_lines))
        if unfulfillable_lines:
            # Cancel these lines
            with self.statistics() as stats:
                unfulfillable_lines.with_context(cancelled_stock_shortage=True).action_cancel()

            _logger.info(
                "Sale lines on orders %s cancelled in %.2fs, %d queries, due to" " stock shortage,",
                ", ".join(unfulfillable_lines.mapped("order_id.name")),
                stats.elapsed,
                stats.count,
            )

            cancelled_sales = unfulfillable_lines.mapped("order_id").filtered(
                lambda x: x.state == "cancel"
            )
            if cancelled_sales:
                _logger.info(
                    "Sales %s cancelled due to missing stock",
                    ", ".join(cancelled_sales.mapped("name")),
                )

        return unfulfillable_lines

    def _find_unfulfillable_order_lines(self, batch_size=1000):
        """Find unfullfilable order lines due to lack of stock."""
        Location = self.env['stock.location']
        OrderLine = self.env["sale.order.line"]
        Quant = self.env['stock.quant']

        # Create empty record sets for SO lines
        unfulfillable_lines = OrderLine.browse()

        _logger.info("Checking orders to cancel due to stock shortage")
        # Get unreserved stock for each product in locations
        locations = Location.get_available_stock_locations()
        stock = defaultdict(int)

        for r, batch in self.batched(size=batch_size):
            _logger.info("Checking orders %d-%d", r[0], r[-1])
            # Cache the needed fields and only the needed fields
            # This code has to process tens of thousands of sale order lines
            # and hundreds of thousands of stock moves.
            # Caching too much is expensive here because of the sheer number of
            # records processed: Odoo's field loading becomes a bottleneck and
            # memory usage skyrockets.
            # Caching too little is also expensive since:
            #  * cache misses cause unused fields to be loaded in due to
            #    prefetching, which leads to overcaching, described above
            #  * cache misses for stock move fields result in hundreds of small
            #    loads per batch, which is inefficient due to overheads
            # For non-relational fields, read() is used instead of mapped()
            # because it allows for loading of specific fields, whereas
            # mapped() will load in as many fields as it can due to prefetching.
            # with_context(prefetch_fields=False) could be used with mapped()
            # but is limited to a single column at a time.
            batch.mapped("order_line")
            batch.mapped("order_line").read(
                ["is_cancelled", "product_id", "product_uom_qty"], load="_classic_write"
            )
            batch.mapped("order_line.move_ids")
            batch.mapped("order_line.move_ids").read(["state"], load="_classic_write")
            # NB: Using with_context(prefetch_fields=False) then
            #     mapped('order_line.move_ids.state') results in unwanted
            #     extra SQL queries. mapped('order_line.move_ids') followed by
            #     with_context and mapped('state') does not.

            for order in batch:
                # Loop SO lines and deduct from stock dict, add order lines to
                # can or cant fulfill record sets
                # If this code is modified, the caching above needs to be
                # kept up to date to ensure good performance
                for line in order.order_line.filtered(lambda x: not x.is_cancelled):

                    # If any of the mls are done or assigned then skip this line
                    line_states = line.mapped("move_ids.state")
                    skip_states = ("assigned", "done", "cancel")
                    if any(x in line_states for x in skip_states):
                        continue

                    product = line.product_id

                    if product not in stock.keys():
                        stock[product] = Quant.get_available_quantity(product, locations)
                    qty_ordered = line.product_uom_qty
                    if stock[product] >= qty_ordered:
                        stock[product] = stock[product] - qty_ordered
                    else:
                        unfulfillable_lines |= line

            # Empty cached stuff
            batch.invalidate_cache()

        return unfulfillable_lines

    def _find_unfulfillable_orders(self, batch_size=1000):
        """Find unfullfilable orders due to lack of stock."""
        unfulfillable_lines = self._find_unfulfillable_order_lines(batch_size)
        return unfulfillable_lines.mapped("order_id")

    def check_delivered(self):
        """ Update sale orders state based on the states of their related
            pickings.
            An order is considered cancelled when all its terminal pickings are
            cancelled and is considered done when all terminal pickings are in a
            terminal state (at least one of which is in state done).
        """
        for order in self:
            last_pickings = order.picking_ids.filtered(lambda p: len(p.u_next_picking_ids) == 0)
            completed_last_pickings = last_pickings.filtered(
                lambda p: p.state in ["done", "cancel"]
            )
            cancelled_last_pickings = last_pickings.filtered(lambda p: p.state == "cancel")
            if last_pickings == cancelled_last_pickings and \
                not self.env.context.get("disable_sale_cancel", False):
                order.with_context(from_sale=True).action_cancel()
            elif last_pickings == completed_last_pickings:
                order.action_done()

    def action_cancel(self):
        """Override to cancel by moves instead of by pickings"""
        self.mapped("order_line").action_cancel()
        return self.write({"state": "cancel"})

    def check_state_cancelled(self):
        to_cancel = self.browse()
        for order in self.filtered(lambda o: o.state not in ["done", "cancel"]):
            non_cancelled = order.order_line.filtered(lambda l: not l.is_cancelled)
            if len(non_cancelled) == 0:
                to_cancel |= order
        to_cancel.write({"state": "cancel"})

    @api.model
    def confirm_if_due(self):
        """
        Confirm sale orders in self that are due to be confirmed
        If no orders passed into self, will confirm all unconfirmed orders

        Returns recordset of orders where confirmation was attempted
        """
        days = self.env.ref("stock.warehouse0").u_so_auto_confirm_ahead_days
        unconfirmed_states = ("draft", "sent")
        unconfirmed_so = self or self.search([("state", "in", unconfirmed_states)])

        # If ahead days set to -1, confirm all.
        if days == -1:
            return unconfirmed_so.action_confirm()

        to_date = fields.Datetime.to_string(date.today() + timedelta(days=days))
        so_to_confirm = unconfirmed_so.filtered(lambda so: so.requested_date <= to_date)
        return so_to_confirm.action_confirm()

    def get_current_demand(self, products=None):
        """ Get current demand created by confirmed Sale Orders
        per product - regardless of expected delivery date

        Returns defaultdict(int, {product.product(1,): 12.0})
        """
        OrderLine = self.env["sale.order.line"]

        # Get order lines
        domain = [("state", "=", "sale"), ("is_cancelled", "=", False)]
        if products:
            domain.append(("product_id", "in", products.ids))
        # Override the search order since the default model order can involve
        # joins, which perform poorly, and the order does not matter here.
        order_lines = OrderLine.search(domain, order="id")
        demand = defaultdict(int)

        for r, batch in order_lines.batched(size=1000):
            # Cache the needed fields and only the needed fields
            # See cancel_sale_orders_without_availability for details
            batch.read(["is_cancelled", "product_id", "product_uom_qty"], load="_classic_write")
            batch.mapped("move_ids")
            batch.mapped("move_ids").read(["state"], load="_classic_write")
            for line in batch:
                # If any of the moves are done or cancelled then skip this line
                line_states = line.mapped("move_ids.state")
                if any(x in line_states for x in ("done", "cancel")):
                    continue
                product = line.product_id
                demand[product] += line.product_uom_qty

            # Empty cached stuff
            batch.invalidate_cache()

        return demand

    def action_confirm(self):
        """ Override to disable tracking by default """
        return super(SaleOrder, self.with_context(tracking_disable=True)).action_confirm()

    def confirm_orders(self, size=1000):
        """Attempt to confirm sale orders.

        If self is empty, find orders to confirm via _get_confirmation_domain.
        Otherwise, attempt to confirm orders in self.

        This is done in batches to reduce the chance of concurrency errors
        when confirming large numbers of orders at once. If one batch fails
        the other batches may still be confirmed, attempting to maximise the number of
        orders that may be confirmed.
        """

        def extract_exception_data(err):
            """Extract information from an exception for later reporting."""
            tbe = traceback.TracebackException.from_exception(err)
            trace = "".join(tbe.format())
            data = "{}\n{}".format(str(err), trace)
            return data

        exception_data = []
        # Getting value of MAX_TRIES_ON_CONCURRENCY_FAILURE from system parameters,
        # will allow us to be flexible to change on fly if needed and not hard coded
        MAX_TRIES_ON_CONCURRENCY_FAILURE = int(self.env["ir.config_parameter"].sudo().get_param(
            "udes_sale_stock.max_tries_on_concurrency_failure", 5))

        if self:
            to_confirm = self
        else:
            to_confirm = self.search(self._get_confirmation_domain())

        for _, batch in to_confirm.batched(size=size):
            tries = 0
            while True:
                try:
                    with self.env.cr.savepoint():
                        batch.with_context(recompute=False).action_confirm()
                        batch.recompute()
                        break
                except OperationalError as e:
                    self.invalidate_cache()
                    if e.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                        raise
                    if tries >= MAX_TRIES_ON_CONCURRENCY_FAILURE:
                        _logger.info(
                            "%s, maximum number of tries reached" % errorcodes.lookup(e.pgcode)
                        )
                        break
                    tries += 1
                    wait_time = 1
                    _logger.info(
                        "%s, retry %d/%d in %.04f sec..."
                        % (
                            errorcodes.lookup(e.pgcode),
                            tries,
                            MAX_TRIES_ON_CONCURRENCY_FAILURE,
                            wait_time,
                        )
                    )
                    time.sleep(wait_time)
                except Exception as e:
                    _logger.exception("Error confirming orders.")
                    self.invalidate_cache()
                    exception_data.append(extract_exception_data(e))
                    break
            if tries >= MAX_TRIES_ON_CONCURRENCY_FAILURE:
                break

            # Incrementally commit to confirm orders as soon as possible and
            # allow serialisation error to propagate.
            self.env.cr.commit()
            self.invalidate_cache()
        if exception_data:
            # Raise an exception that includes details of the exceptions that
            # have been suppressed, in case we want to expose this information
            # somewhere else.
            collected_exceptions = "\n\n".join(exception_data)
            _logger.error(collected_exceptions)
            raise exceptions.CombinedException(
                "At least one error occurred while confirming orders.",
                collected_exceptions=collected_exceptions
            ) from None

        return True

    def merge_confirm_orders_reserve_stock(
        self,
        confirm_orders_batch_size=1000,
        confirm_orders_commit_size=1000,
        finish=False,
    ):
        """Confirm Orders and Reserve Stock in a single cron job so the two processes can be
        run simultaneously.
        The process is described below:
        1. Reserve stock if there are no orders to confirm.
        2. Split all orders to confirm in sizes with confirm_orders_batch_size.
        3. For every orders_to_confirm batch, confirm and commit
            orders within confirm_orders_commit_size.
        4. After confirming orders_to_confirm batch, reserve stock.
        5. If needed to confirm only 1 confirm_orders_batch_size finish variable
        will get out and finish the cron job.
        6. Not confirmed orders and not reserved stock will be picked in the
        next cron job if finish is set to true.
        :param int confirm_orders_batch_size:
            Number of orders to be confirmed before reserving stock.
        :param int confirm_orders_commit_size:
            Number of orders to be confirmed before committing.
        :param boolean finish:
            Flag if True will finish the cron job after the first iteration and pick the
            remaining orders to confirm on the next cron run.
        """
        SaleOrder = self.env["sale.order"]
        StockPicking = self.env["stock.picking"]

        orders_to_confirm = SaleOrder.get_orders_to_confirm()
        # If there aren't any orders to confirm just run the reserve stock cron
        if not orders_to_confirm:
            StockPicking.reserve_stock()
        for _, batch in orders_to_confirm.batched(size=confirm_orders_batch_size):
            # Confirm orders cron and reserve stock after for every confirm_orders_batch_size
            batch.confirm_orders(size=confirm_orders_commit_size)
            StockPicking.reserve_stock()
            # Break the for loop in case we want to finish the cron job after the first iteration
            if finish:
                break

        return True

    def _get_confirmation_domain(self):
        """Returns the domain for sale orders to attempt confirmation."""
        return [("state", "=", "draft")]

    def get_orders_to_confirm(self):
        """ Getting orders to confirm. Placing into a method in order to be easier to override"""
        return self.search(self._get_confirmation_domain())
