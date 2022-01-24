# -*- coding: utf-8 -*-
import time
from psycopg2 import OperationalError, errorcodes
from collections import defaultdict

from odoo import fields, models, _, api
from odoo.exceptions import UserError, ValidationError

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

    def _reserve_stock_assign(self):
        """Perform assign of the pickings at the move level because refactoring
        may change the pickings.
        This is a function so it can be extended and/or overriden.
        """
        # Assign at the move level disabling refactoring
        moves = self.move_lines
        moves._action_assign()
        return moves.picking_id

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
                    pickings = self.filtered(
                        lambda p: p.picking_type_id == picking_type
                    )
                    # Removed processed pickings from self
                    pickings -= processed
                else:
                    domain = base_domain[:]
                    if processed:
                        domain.append(("id", "not in", processed.ids))
                    pickings = Picking.search(domain, limit=limit)

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
                                if not mls:
                                    # construct error message, report only products
                                    # that are unreservable.
                                    moves = unsatisfied.move_lines.filtered(unsatisfied_state)
                                    products = moves.product_id.default_code
                                    picks = moves.picking_id.name
                                    msg = (
                                        f"Unable to reserve stock for products {products} "
                                        f"for pickings {picks}."
                                    )
                                    raise UserError(msg)
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
                                "%s, maximum number of tries reached"
                                % errorcodes.lookup(e.pgcode)
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
