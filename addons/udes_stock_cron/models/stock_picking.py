# -*- coding: utf-8 -*-
from odoo import fields, models, _, api
from collections import defaultdict
from odoo.exceptions import UserError, ValidationError
from psycopg2 import OperationalError, errorcodes

import logging
_logger = logging.getLogger(__name__)


PG_CONCURRENCY_ERRORS_TO_RETRY = (
    errorcodes.LOCK_NOT_AVAILABLE,
    errorcodes.SERIALIZATION_FAILURE,
    errorcodes.DEADLOCK_DETECTED,
)
MAX_TRIES_ON_CONCURRENCY_FAILURE = 5

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    batch_id = fields.Many2one("stock.picking.batch", copy=True)

    def _reserve_stock_assign(self):
        """Perform assign of the pickings at the move level because refactoring
        may change the pickings.
        This is a function so it can be extended and/or overriden.
        """
        # Assign at the move level disabling refactoring
        moves = self.mapped("move_lines")
        moves.with_context(lock_batch_state=True, disable_move_refactor=True)._action_assign()

        # Unreserve any partially reserved lines if not allowed by the picking type
        moves._unreserve_partial_lines()

        # Refactor after unreserving
        refactored_moves = moves._action_refactor(stage="assign")

        return refactored_moves.mapped("picking_id")

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
            picking_types = self.mapped("picking_type_id")
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
            base_domain = [("picking_type_id", "=", picking_type.id), ("state", "=", "confirmed")]
            limit = 1
            processed = Picking.browse()
            by_type = lambda x: x.picking_type_id == picking_type

            while reserve_all or to_reserve > 0:

                if self:
                    # Removed processed pickings from self
                    pickings = self.filtered(by_type) - processed
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

                batch = pickings.mapped("batch_id")
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

                            unsatisfied = pickings.filtered(
                                lambda x: x.state not in ["assigned", "cancel", "done"]
                            )
                            mls = pickings.mapped("move_line_ids")
                            if unsatisfied:
                                # Unreserve if the picking type cannot handle partials or it
                                # can but there is nothing allocated (no stock.move.lines)
                                if not picking_type.u_handle_partials or not mls:
                                    # construct error message, report only products
                                    # that are unreservable.
                                    not_done = lambda x: x.state not in (
                                        "done",
                                        "assigned",
                                        "cancel",
                                    )
                                    moves = unsatisfied.mapped("move_lines").filtered(not_done)
                                    products = moves.mapped("product_id.default_code")
                                    picks = moves.mapped("picking_id.name")
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
                to_reserve -= len(mls.mapped("picking_id"))

                if self:
                    # Only process the specified pickings
                    break
            _logger.info("Reserving stock for picking type %r completed.", picking_type)
        return
    
    def apply_drop_location_policy(self):
        """Apply suggested locations to move lines
        raise ValidationError: if the policy set does not have
                               _allow_preprocess set
        """
        by_pack_or_single = lambda ml: ml.package_id.package_id or ml.package_id or ml.id

        for pick in self:
            self.check_policy_for_preprocessing(pick.picking_type_id.u_drop_location_policy)
            # Group by pallet or package
            for _pack, mls in pick.move_line_ids.groupby(by_pack_or_single):
                locs = pick.get_suggested_locations(mls)
                if locs:
                    mls.write({"location_dest_id": locs[0].id})

    def check_policy_for_preprocessing(self, policy):
        """ "Check policy allows pre processing as not all polices
        can be used in this way
        """
        func = getattr(self, "_get_suggested_location_" + policy, None)

        if not hasattr(func, "_allow_preprocess"):
            raise ValidationError(
                _("This policy(%s) is not meant to be used in " "preprocessing") % policy
            )
    
    def get_suggested_locations(self, move_line_ids, limit=None, sort=True):
        """Dispatch the configured suggestion location policy to
        retrieve the suggested locations
        """
        result = self.env["stock.location"]

        # WS-MPS: use self.ensure_one() and don't loop (self is used in all but
        # one place), or suggest locations for the move lines of the picking,
        # use picking instead of self inside the loop and ?intersect? result.
        for picking in self:
            policy = picking.picking_type_id.u_drop_location_policy

            if policy:
                if (
                    move_line_ids
                    and picking.picking_type_id.u_drop_location_preprocess
                    and not move_line_ids.any_destination_locations_default()
                ):
                    # The policy has been preprocessed this assumes the
                    # the policy is able to provide a sensible value (this is
                    # not the case for every policy)
                    # Use the preselected value
                    result = self._get_suggested_location_exactly_match_move_line(move_line_ids)

                    # Just to prevent running it twice
                    if not result and policy == "exactly_match_move_line":
                        return result

                # If the pre-selected value is blocked
                if not result:
                    func = getattr(self, "_get_suggested_location_" + policy, None)
                    if func:
                        # The signature of each "get suggested location" method may not
                        # match, so inspect the method and only pass in the expected args
                        expected_args = inspect.getfullargspec(func)[0]
                        keys = ["move_line_ids", "limit", "sort"]
                        local_vars = locals()
                        kwargs = {x: local_vars[x] for x in keys if x in expected_args}
                        result = func(**kwargs)
                        # If result is sorted by the suggest method, don't re-sort it
                        if "sort" in expected_args:
                            sort = False
        if sort:
            return result.sorted(lambda l: l.name)
        else:
            return result
    
    def _get_suggested_location_exactly_match_move_line(self, move_line_ids):
        self._check_picking_move_lines_suggest_location(move_line_ids)
        location = move_line_ids.mapped("location_dest_id")

        location.ensure_one()

        if location.u_blocked or location.usage == "view":
            return self.env["stock.location"]

        return location

    def _check_picking_move_lines_suggest_location(self, move_line_ids):
        pick_move_lines = self.mapped("move_line_ids").filtered(lambda ml: ml in move_line_ids)

        if len(pick_move_lines) != len(move_line_ids):
            raise ValidationError(
                _(
                    "Some move lines not found in picking %s to suggest "
                    "drop off locations for them." % self.name
                )
            )

    def _should_reserve_full_packages(self):
        """Method to determine if picking should reserve entire packages"""
        self.ensure_one()
        return self.picking_type_id.u_reserve_as_packages

    def _reserve_full_packages(self):
        """
        If the picking type of the picking in self has full package
        reservation enabled, partially reserved packages are
        completed.
        """
        Quant = self.env["stock.quant"]
        MoveLine = self.env["stock.move.line"]

        # do not reserve full packages when bypass_reserve_full packages
        # is set in the context as True
        if not self.env.context.get("bypass_reserve_full_packages"):
            for picking in self.filtered(lambda p: p._should_reserve_full_packages()):
                all_quants = Quant.browse()
                remaining_qtys = defaultdict(int)

                # get all packages
                packages = picking.mapped("move_line_ids.package_id")
                for package in packages:
                    move_lines = picking.mapped("move_line_ids").filtered(
                        lambda ml: ml.package_id == package
                    )
                    # TODO: merge with assert_reserved_full_package
                    pack_products = frozenset(package._get_all_products_quantities().items())
                    mls_products = frozenset(move_lines._get_all_products_quantities().items())
                    if pack_products != mls_products:
                        # move_lines do not match the quants
                        pack_mls = MoveLine.search(
                            [
                                ("package_id", "child_of", package.id),
                                ("state", "not in", ["done", "cancel"]),
                            ]
                        )
                        other_pickings = pack_mls.mapped("picking_id") - picking
                        if other_pickings:
                            raise ValidationError(
                                _("The package is reserved in other pickings: %s")
                                % ",".join(other_pickings.mapped("name"))
                            )

                        quants = package._get_contained_quants()
                        all_quants |= quants
                        for product, qty in quants.group_quantity_by_product(
                            only_available=True
                        ).items():
                            remaining_qtys[product] += qty
                if remaining_qtys:
                    # Context variables:
                    # - filter the quants used in _create_moves() to be
                    # the ones of the packages to be completed
                    # - add bypass_reserve_full_packages at the context
                    # to avoid to be called again inside _create_moves()
                    picking.with_context(
                        bypass_reserve_full_packages=True, quant_ids=all_quants.ids
                    )._create_moves(
                        remaining_qtys,
                        values={"priority": picking.priority},
                        confirm=True,
                        assign=True,
                    )

    def can_handle_partials(self, **kwargs):
        self.ensure_one()
        return self.picking_type_id.u_handle_partials
    
    @api.depends("move_type", "move_lines.state", "move_lines.picking_id")
    def _compute_state(self):
        """Prevent pickings to be in state assigned when not able to handle
        partials, so they should remain in state waiting or confirmed until
        they are fully assigned.

        Add the flag 'computing_state' when we call can_handle_partials here to
        distinguish it from other calls.
        """
        move_lines = self.move_lines.filtered(lambda move: move.state not in ["cancel", "done"])
        if move_lines and not self.can_handle_partials(computing_state=True):
            relevant_move_state = move_lines._get_relevant_state_among_moves()
            if relevant_move_state == "partially_available":
                if self.u_prev_picking_ids:
                    self.state = "waiting"
                else:
                    self.state = "confirmed"
                return

        super()._compute_state()


