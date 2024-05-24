from collections import defaultdict

from odoo import models, _
from odoo.exceptions import UserError
from odoo.addons.udes_common.tools import odoo_retry

import logging

_logger = logging.getLogger(__name__)


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

    def reserve_stock(self, batch_size=100):
        """
        Reserve stock according to the number of reservable pickings.

        If this method is called on an empty recordset it will attempt to
        reserve stock for all eligible picking types.  If the recordset is not
        empty, it will reserve stock for the picks in the recordset, and it
        will be the callers responsibility to make sure that the pickings belong
        to at most one batch, otherwise this method cannot respect the priority
        order of pickings, in this case the behaviour of this method is undefined.

        Params:
        batch_size: (int) The number of pickings to retrieve in each fetch from
                          the database if the number of reservable pickings is
                          unlimited.
        """
        PickingType = self.env["stock.picking.type"]
        Quant = self.env["stock.quant"]

        # Ensure all quants are merged and empty ones are deleted before starting to reserve stock.
        # sudoing is handled by _quant_tasks.
        Quant._quant_tasks()
        # Getting here from a wizard - will have recordsets. CRON jobs - will be emptysets.
        using_wizard = len(self) > 0
        picking_types = (
            self.picking_type_id
            if using_wizard
            else PickingType.search([("active", "=", True), ("u_num_reservable_pickings", "!=", 0)])
        )

        for picking_type in picking_types:
            _logger.info("Reserving stock for picking type %r.", picking_type)
            self.reserve_stock_for_picking_type(picking_type, using_wizard, batch_size)
            _logger.info("Reserving stock for picking type %r completed.", picking_type)
        return

    def reserve_stock_for_picking_type(self, picking_type, using_wizard, batch_size):
        """
        Reserve stock for a particular picking type.

        The picking type flags for reserving complete batches and handling
        partial batches will be respected.

        The number of reservable pickings is defined on the picking type.
        0 reservable pickings means this function should not reserve stock
        -1 reservable picking means all reservable stock should be reserved.

        We will either reserve up to the reservation limit or until all
        available picks have been reserved, depending on the value of
        u_num_reservable_pickings.
        However we must also take into account the atomic batch reservation
        flag (u_reserve_batches) and the handle partial flag (u_handle_partials).
        """

        def generate_pickings():
            """
            Abstract iteration over fetched pickings.
            If self is not empty, we yield the pickings by picking type, removing processed ones.
            The state of these pickings is determined by the caller. The caller is also responsible
            for ensuring the pickings in self belong to at most one batch.

            If self is empty, we yield one by one all pickings which are not processed,
            as we can not assume they are from the same batch.
            """
            while True:
                if using_wizard:
                    yield self.filtered(lambda p: p.picking_type_id == picking_type) - processed
                else:
                    domain = [
                        ("picking_type_id", "=", picking_type.id),
                        ("state", "=", "confirmed"),
                    ]
                    if processed:
                        domain.append(("id", "not in", processed.ids))
                    pickings = Picking.search(domain, limit=batch_size)
                    if not pickings:
                        break
                    yield from pickings

        Picking = self.env["stock.picking"]
        # Reserve batches 'atomically' i.e reserve pickings until all pickings in a batch have
        # been assigned, even if we exceed the number of reservable pickings.
        # If the u_handle_partials is False, we should not reserve stock
        # if the batch can not be completely reserved.
        to_reserve = picking_type.u_num_reservable_pickings
        processed = Picking.browse()

        pickings_to_reserve = generate_pickings()
        # Reserve stock until there is none left to reserve (or -1 - reserve all)
        while to_reserve != 0:
            pickings = next(pickings_to_reserve, Picking.browse())
            _logger.info(f"Reserving stock for pickings {pickings}.")
            if not pickings:
                break  # No pickings left to process. Exit the loop.

            if pickings.batch_id:
                if pickings.batch_id.state == "draft":
                    # Continue the loop (skip batch and don't process its pickings).
                    processed |= pickings.batch_id.picking_ids
                    continue
                if picking_type.u_reserve_batches:
                    # Process the batches pickings
                    pickings = pickings.batch_id.picking_ids

            # Pre-pass to remove unprocessable pickings
            unreservable_moves = pickings._find_unreservable_moves(return_fast=bool(using_wizard))
            if unreservable_moves:
                moves = pickings.move_lines
                moves_todo = (
                    moves.filtered(lambda m: m.state in ["confirmed", "draft"]) - unreservable_moves
                )
                if not picking_type.u_handle_partials:
                    # Add to processed to skip reservation.
                    processed |= pickings

                    if using_wizard:
                        self.raise_insufficiency_error(unreservable_moves)
                    continue
                elif not moves_todo:
                    # Add to processed to skip reservation.
                    processed |= pickings
                    continue

            # Actually reserve the stock, inside a retry loop to handle potential concurrency issues
            # Note that it is this loop that's responsible for handling try count.
            # -1 is UserError raised by odoo_retry - but only if using_wizard is True.
            data = odoo_retry(
                self,
                pickings._process_pickings,
                MAX_TRIES_ON_CONCURRENCY_FAILURE,
                raise_usererrors=using_wizard,
            )()
            tries = data.get("tries")
            processed |= data.get("newly_processed", pickings)
            if tries == -1:
                continue
            if tries >= MAX_TRIES_ON_CONCURRENCY_FAILURE:
                break

            # Incrementally commit to release picks as soon as possible and
            # allow serialisation error to propagate to respect priority order
            self.env.cr.commit()

            # Determine reserved pickings from the move lines which got processed
            to_reserve -= len(data.get("mls").picking_id)

            if using_wizard:
                # Only perform one iteration if we had all of our pickings scoped in to begin with
                break

    def _reserve_stock_assign(self):
        """Perform assign of the pickings at the move level because refactoring
        may change the pickings.
        This is a function so it can be extended and/or overriden.
        """
        # Assign at the move level disabling refactoring
        moves = self.move_lines
        assigned_moves = moves._action_assign()
        return assigned_moves.picking_id

    def raise_insufficiency_error(self, moves):
        """Helper function to raise error for insufficent stock."""
        products = moves.product_id.name_get()
        picks = moves.mapped("picking_id.name")
        product_names = ", ".join(sorted({p[1] for p in products}))
        raise UserError(
            _("Unable to reserve stock for products %s for pickings %s.") % (product_names, picks)
        )

    def _process_pickings(self):
        """
        Helper function to actually process the pickings in `self`.
        Called while being wrapped by odoo_retry, hence the return values being a dict.
        """
        unsatisfied_state = lambda p: p.state not in ("assigned", "cancel", "done")
        newly_processed = self._reserve_stock_assign()
        self.batch_id._compute_state()

        unsatisfied = newly_processed.filtered(unsatisfied_state)

        mls = newly_processed.move_line_ids
        if unsatisfied:
            # Unreserve if the picking type cannot handle partials or it
            # can but there is nothing allocated (no stock.move.lines)
            if not self.picking_type_id.u_handle_partials or not mls:
                # construct error message, report only products
                # that are unreservable.
                moves = unsatisfied.move_lines.filtered(unsatisfied_state)
                self.raise_insufficiency_error(moves)
        return {"newly_processed": newly_processed, "mls": mls}
