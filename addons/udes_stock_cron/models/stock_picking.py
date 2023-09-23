import time
from psycopg2 import OperationalError, errorcodes
from collections import defaultdict

from odoo import models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


PG_CONCURRENCY_ERRORS_TO_RETRY = (
    errorcodes.LOCK_NOT_AVAILABLE,
    errorcodes.SERIALIZATION_FAILURE,
    errorcodes.DEADLOCK_DETECTED,
)
MAX_TRIES_ON_CONCURRENCY_FAILURE = 5


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _find_unreservable_moves(self, batch_size=1000, return_fast=False):
        """
        Find moves for which there is insufficient stock.

        The u_handle_partials flag on the picking type is respected: if it is
        True, partially reservable lines will not be reported.
        """
        # This method is patterned on SaleOrder._find_unfulfillable_order_lines
        # in udes_sale_stock.  Changes applied there should be considered for
        # this method too.
        Move = self.env["stock.move"]
        Quant = self.env["stock.quant"]

        # Create empty record sets for moves.
        unreservable_moves = Move.browse()

        location = self.picking_type_id.default_location_src_id
        stock_for_products = defaultdict(int)
        skip_states = ("assigned", "done", "cancel")
        level = logging.DEBUG if len(self) == 1 else logging.INFO
        _logger.log(level, _("Checking reservability for %d pickings."), len(self))
        for r, batch in self.batched(size=batch_size):
            _logger.log(level, "Checking pickings %d-%d", r[0], r[-1])
            # Cache the needed fields and only the needed fields
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
            batched_pickings = batch.with_context(prefetch_fields=False)
            batched_pickings.move_lines.read(
                ["product_id", "product_uom_qty", "state"], load="_classic_write"
            )

            for picking in batched_pickings:
                # Loop moves and deduct from stock_for_products dict
                # If this code is modified, the caching above needs to be
                # kept up to date to ensure good performance
                for move in picking.move_lines.filtered(lambda m: m.state not in skip_states):
                    product = move.product_id

                    if product not in stock_for_products.keys():
                        stock_for_products[product] = Quant.get_available_quantity(
                            product,
                            location,
                        )
                    qty_ordered = move.product_uom_qty
                    if stock_for_products[product] <= 0 or (
                        stock_for_products[product] < qty_ordered
                        and not picking.picking_type_id.u_handle_partials
                    ):
                        unreservable_moves |= move
                        if return_fast:
                            return unreservable_moves
                    stock_for_products[product] -= qty_ordered

        return unreservable_moves

    def _reserve_stock_assign(self):
        """Perform assign of the pickings at the move level because refactoring
        may change the pickings.
        This is a function so it can be extended and/or overriden.
        """
        # Assign at the move level disabling refactoring
        moves = self.move_lines
        assigned_moves = moves._action_assign()
        return assigned_moves.mapped("picking_id")

    def reserve_stock(self):
        """
        Reserve stock according to the number of reservable pickings.
        If this method is called on an empty recordset it will attempt to
        reserve stock for all eligible picking types.  If the recordset is not
        empty, it will reserve stock for the picks in the recordset. If the
        recordset is not empty, it is the callers responsibility to make sure
        that the pickings belong to at most one batch, otherwise this method
        cannot respect the priority order of pickings, in this case the
        behaviour of this method is undefined.
        In either scenario the picking type flags for reserving complete
        batches and handling partial batches are respected.
        The number of reservable pickings is defined on the picking type.
        0 reservable pickings means this function should not reserve stock
        -1 reservable picking means all reservable stock should be reserved.
        """

        Picking = self.env["stock.picking"]
        PickingType = self.env["stock.picking.type"]
        Quant = self.env["stock.quant"]

        def raise_insufficiency_error(moves):
            """Helper function to raise error for insufficent stock."""
            products = moves.product_id.name_get()
            picks = moves.mapped("picking_id.name")
            product_names = ", ".join(sorted({p[1] for p in products}))
            raise UserError(
                _("Unable to reserve stock for products %s for pickings %s.")
                % (product_names, picks)
            )

        # Making sure that quants are merged and deleted the empty ones before starting the reserve
        # stock. No need to run with sudo as the methods inside _quant_tasks have already sudo
        # where needed.
        Quant._quant_tasks()

        if self:
            picking_types = self.picking_type_id
        else:
            picking_types = PickingType.search(
                [("active", "=", True), ("u_num_reservable_pickings", "!=", 0)]
            )

        # We will either reserve up to the reservation limit or until all
        # available picks have been reserved, depending on the value of
        # u_num_reservable_pickings.
        # However we must also take into account the atomic batch reservation
        # flag (u_reserve_batches) and the handle partial flag
        # (u_handle_partials).

        for picking_type in picking_types:
            _logger.info("Reserving stock for picking type %r.", picking_type)

            # We want to reserve batches atomically, that is we will
            # reserve pickings until all pickings in a batch have been
            # assigned, even if we exceed the number of reservable pickings.
            # However, the value of the handle partial flag is false we
            # should not reserve stock if the batch cannot be completely
            # reserved.
            to_reserve = picking_type.u_num_reservable_pickings
            reserve_all = to_reserve == -1
            base_domain = [
                ("picking_type_id", "=", picking_type.id),
                ("state", "=", "confirmed"),
            ]
            limit = 1
            processed = Picking.browse()
            unsatisfied_state = lambda p: p.state not in ("assigned", "cancel", "done")

            while reserve_all or to_reserve > 0:
                if self:
                    pickings = self.filtered(lambda p: p.picking_type_id == picking_type)
                    # Removed processed pickings from self
                    pickings -= processed
                else:
                    domain = base_domain[:]
                    if processed:
                        domain.append(("id", "not in", processed.ids))
                    pickings = Picking.search(domain, limit=limit)

                _logger.info(f"Reserving stock for pickings {pickings}.")
                if not pickings:
                    # No pickings left to process.
                    # If u_num_reservable_pickings is -1, or there are
                    # fewer available pickings that the limit, the loop must
                    # terminate here.
                    break

                batch = pickings.batch_id
                if batch and batch.state == "draft":
                    # Add to seen pickings so that we don't try to process
                    # this batch again.
                    processed |= batch.picking_ids
                    continue

                if batch and picking_type.u_reserve_batches:
                    pickings = batch.picking_ids

                # Check for available stock and add pickings which we cannot
                # fulfill to the processed recordset. The logic here
                # should mirror that within the savepoint below, expect here we
                # do not have the move lines.
                unreservable_moves = pickings._find_unreservable_moves(return_fast=bool(self))
                if unreservable_moves:
                    moves = pickings.move_lines
                    moves_todo = (
                        moves.filtered(lambda m: m.state in ["confirmed", "draft"])
                        - unreservable_moves
                    )
                    if not picking_type.u_handle_partials:
                        # Add to processed to skip reservation.
                        processed |= pickings

                        if self:
                            raise_insufficiency_error(unreservable_moves)
                        continue
                    elif not moves_todo:
                        # Add to processed to skip reservation.
                        processed |= pickings
                        continue

                # MPS: mimic Odoo's retry behaviour
                tries = 0
                while True:
                    try:
                        with self.env.cr.savepoint():
                            pickings = pickings._reserve_stock_assign()
                            batch._compute_state()

                            processed |= pickings

                            unsatisfied = pickings.filtered(unsatisfied_state)

                            mls = pickings.move_line_ids
                            if unsatisfied:
                                # Unreserve if the picking type cannot handle partials or it
                                # can but there is nothing allocated (no stock.move.lines)
                                if not picking_type.u_handle_partials or not mls:
                                    # construct error message, report only products
                                    # that are unreservable.
                                    moves = unsatisfied.move_lines.filtered(unsatisfied_state)
                                    raise_insufficiency_error(moves)
                            break
                    except UserError as e:
                        self.invalidate_cache()
                        # Only propagate the error if the function has been
                        # manually triggered
                        if self:
                            raise e
                        tries = -1
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
                if tries == -1:
                    continue
                if tries >= MAX_TRIES_ON_CONCURRENCY_FAILURE:
                    break

                # Incrementally commit to release picks as soon as possible and
                # allow serialisation error to propagate to respect priority
                # order
                self.env.cr.commit()
                # Only count as reserved the number of pickings at mls
                to_reserve -= len(mls.picking_id)

                if self:
                    # Only process the specified pickings
                    break
            _logger.info("Reserving stock for picking type %r completed.", picking_type)
        return
