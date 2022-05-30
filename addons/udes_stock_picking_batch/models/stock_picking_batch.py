import logging
from itertools import chain

from odoo import models, fields, _, api
from odoo.exceptions import UserError, ValidationError
from .common import PRIORITIES
from odoo.addons.udes_stock.models.common import get_next_name

_logger = logging.getLogger(__name__)


class StockPickingBatch(models.Model):
    _name = "stock.picking.batch"
    _inherit = ["stock.picking.batch", "mixin.stock.model"]

    user_id = fields.Many2one(
        "res.users",
        states={
            "draft": [("readonly", False)],
            "waiting": [("readonly", False)],
            "ready": [("readonly", False)],
            "in_progress": [("readonly", False)],
        },
    )
    # Note: state field has been found to recompute itself everytime it was accessed even with store=True
    # lock_batch_state has been put in places to ensure correct behaviour.
    state = fields.Selection(
        selection_add=[("waiting", "Waiting"), ("ready", "Ready"), ("in_progress", "Running")],
        compute="_compute_state",
        store=True,
        ondelete={
            "waiting": lambda spb: spb.write({"state": "draft"}),
            "ready": lambda spb: spb.write({"state": "draft"}),
        },
    )
    picking_ids = fields.One2many(
        "stock.picking",
        "batch_id",
        states={
            "draft": [("readonly", False)],
            "waiting": [("readonly", False)],
            "ready": [("readonly", False)],
            "in_progress": [("readonly", False)],
        },
    )
    u_last_reserved_pallet_name = fields.Char(
        string="Last Pallet Used",
        index=True,
        help="Barcode of the last pallet used for this batch. "
        "If the batch is in progress, indicates the pallet currently in use.",
    )
    u_ephemeral = fields.Boolean(
        string="Ephemeral", help="Ephemeral batches are unassigned if the user logs out."
    )
    priority = fields.Selection(
        selection=PRIORITIES,
        string="Priority",
        store=True,
        index=True,
        readonly=True,
        compute="_compute_priority",
        help="Priority of a batch is the maximum priority of its pickings.",
    )
    u_original_name = fields.Char(
        string="Original Batch Name",
        default="",
        copy=True,
        required=False,
        help="Name of the batch from which this batch was derived",
    )

    @api.constrains("user_id")
    def _compute_state(self):
        """ Compute the state of a batch
            waiting     : At least some picks are not ready
            ready       : All picks are in ready state (assigned)
            in_progress : All picks are ready and a user has been assigned
            done        : All picks are complete (in state done or cancel)

            the other two states are draft and cancel are manual
            to transitions from or to the respective state.
        """
        if self.env.context.get("lock_batch_state"):
            # State is locked so don't do anything
            return

        for batch in self:
            if batch.state in ["draft", "cancel"]:
                # Can not do anything with them don't bother trying
                continue

            if batch.picking_ids:

                ready_picks = batch.ready_picks()
                done_picks = batch.done_picks()
                unready_picks = batch.unready_picks()

                # Figure out state
                if ready_picks and not unready_picks:
                    if batch.user_id:
                        batch.state = "in_progress"
                    else:
                        batch.state = "ready"

                if ready_picks and unready_picks:
                    if batch.user_id:
                        batch.state = "in_progress"
                    else:
                        batch.state = "waiting"

                if done_picks and not ready_picks and not unready_picks:
                    batch.state = "done"
            else:
                batch.state = "done"

    def done_picks(self):
        """ Return done picks from picks or self.picking_ids """
        picks = self.picking_ids
        return picks.filtered(lambda pick: pick.state in ["done", "cancel"])

    def ready_picks(self):
        """ Return ready picks from picks or self.picking_ids """
        picks = self.picking_ids
        return picks.filtered(lambda pick: pick.state == "assigned")

    def unready_picks(self):
        """ Return unready picks from picks or self.picking_ids """
        picks = self.picking_ids
        return picks.filtered(lambda pick: pick.state in ["draft", "waiting", "confirmed"])

    def mark_as_todo(self):
        """Mark as to-do will change the state from draft to waiting.

        This is done without calling action assign.
        """
        _logger.info("User %r has marked %r as todo.", self.env.uid, self)
        not_draft = self.filtered(lambda b: b.state != "draft")
        if not_draft:
            raise UserError(
                _(
                    "The following batches can not be marked as Todo as they are not in the draft state: %s"
                )
                % not_draft.mapped("name")
            )
        self.write({"state": "waiting"})
        self._compute_state()

    def action_confirm(self):
        """Overwrite method action_confirm
           Move batch from draft to waiting.
           Raise error if not in draft and rollback to draft on error in action_assign.
        """
        self.ensure_one()
        if self.state != "draft":
            raise ValidationError(
                _("Batch (%s) is not in state draft can not perform " "action_confirm")
                % ",".join(self.name)
            )
        if not self.picking_ids:
            raise UserError(_("You have to set some pickings to batch."))
        self._check_company()

        pickings_todo = self.picking_ids
        # Set batch to waiting
        self.write({"state": "waiting"})

        try:
            p = pickings_todo.with_context(lock_batch_state=True).action_assign()
            self._compute_state()
            return p
        except:
            # Return all to draft
            self.write({"state": "draft"})
            raise

    @api.constrains("picking_ids")
    def _assign_picks(self):
        """If configured, attempt to assign all the relevant pickings in self"""
        if self.env.context.get("lock_batch_state"):
            # State is locked so don't do anything
            return

        # Get active batches with pickings, apply lock_batch_state here as we do not
        # want to recompute the state just yet as we want to mark pickings assigned first.
        batches = self.with_context(lock_batch_state=True).filtered(
            lambda b: (
                b.state in ["waiting", "in_progress"]
                and b.picking_ids
                and b.picking_type_id.u_auto_assign_batch_pick
            )
        )

        for batch in batches:
            picks_to_assign = batch.picking_ids.filtered(
                lambda p: p.state == "confirmed"
                and p.picking_type_id.u_auto_assign_batch_pick
                and p.move_lines.filtered(
                    lambda move: move.state not in ("draft", "cancel", "done")
                )
            )
            if picks_to_assign:
                picks_to_assign.with_context(lock_batch_state=True).action_assign()
                batch._compute_state()

    def _remove_unready_picks(self):
        """ Remove unready picks from running batches in self, if configured """
        if self.env.context.get("lock_batch_state"):
            # State is locked so don't do anything
            return

        # Get unready picks in running batches
        unready_picks = (
            self.with_context(lock_batch_state=True)
            .filtered(lambda b: b.state in ["waiting", "in_progress"])
            .unready_picks()
        )

        if not unready_picks:
            # Nothing to do
            return

        # Remove unready pick, if configured.
        unready_picks.filtered(lambda p: p.picking_type_id.u_remove_unready_batch)
        unready_picks.write({"batch_id": False, "u_reserved_pallet": False})

    @api.depends("picking_ids.priority")
    def _compute_priority(self):
        for batch in self:
            # Get the old priority of the batch
            old_priority = False
            if not isinstance(batch.id, models.NewId):
                old_priority = batch.read(["priority"])[0]["priority"]
            if batch.picking_ids:
                priorities = batch.picking_ids.mapped("priority")
                new_priority = max(priorities)
            else:
                # If the picking is empty keep the old priority
                new_priority = old_priority
            if new_priority != old_priority:
                batch.priority = new_priority

    def is_valid_location_dest_id(self, location_ref):
        """
        Whether the specified location is a valid putaway location
        for the relevant pickings of the batch. Expects a singleton instance.

        Parameters
        ----------
        location_ref: char
            Location identifier can be the ID, name or the barcode

        Returns a boolean indicating the validity check outcome.
        """
        self.ensure_one()
        Location = self.env["stock.location"]

        try:
            location = Location.get_or_create(location_ref)
        except Exception:
            return False

        done_pickings = self.picking_ids.filtered(lambda p: p.state == "assigned")
        done_move_lines = done_pickings.get_move_lines_done()
        all_done_pickings = done_move_lines.picking_id

        return all(
            [pick.is_valid_location_dest_id(location=location) for pick in all_done_pickings]
        )

    def add_extra_pickings(self, picking_type_id, limit=1):
        """Get the next possible available pickings and add them to the current users batch

        Parameters
        ----------
        picking_type_id : integer
            Id of picking type
        limit: integer
            Location identifier can be the ID, name or the barcode.
            If limit = -1 means unbounded
        """
        Picking = self.env["stock.picking"]

        if not self.u_ephemeral:
            raise ValidationError(_("Can only add work to ephemeral batches"))

        picking_priorities = self.get_batch_priority_group()
        pickings = Picking.search_for_pickings(picking_type_id, picking_priorities, limit=limit)

        if not pickings:
            raise ValidationError(_("No more work to do."))

        picking_type = pickings.picking_type_id
        if picking_type.u_reserve_pallet_per_picking:
            active_pickings = self.picking_ids.filtered(
                lambda p: p.state not in ["draft", "done", "cancel"]
            )
            if len(active_pickings) + len(pickings) > picking_type.u_max_reservable_pallets:
                raise ValidationError(
                    "Only %d pallets may be reserved at a time."
                    % picking_type.u_max_reservable_pallets
                )

        self.check_same_picking_priority(pickings)
        pickings.write({"batch_id": self.id})
        return True

    def get_batch_priority_group(self):
        """Get priority group for this batch based on the pickings' priorities
        Returns list of IDs
        """
        Picking = self.env["stock.picking"]

        if not self.picking_ids:
            raise ValidationError(_("Batch without pickings cannot have a priority group"))

        picking_priority = self.picking_ids[0].priority
        priority_groups = Picking.get_priorities()
        for priority_group in priority_groups:
            priority_ids = [priority["id"] for priority in priority_group["priorities"]]
            if picking_priority in priority_ids:
                return priority_ids
        return None

    def check_same_picking_priority(self, pickings, mode="mobile"):
        """Checks if pickings priorities matches with batch priority

        Args:
            pickings (stock.picking): set of Picking objects
            mode (char): Mode of checking same picking priority
        Return:
            List: Returns list picking priority name which is different than batch priority
        """
        self.ensure_one()
        u_log_batch_picking, user_name = self.get_log_batch_picking_flag()

        old_batch = hasattr(self, "_origin") and self._origin or self
        priority = old_batch.priority
        batch_name = self.name
        diff_priority_pickings = pickings.filtered(lambda r: r.priority != priority).mapped("name")
        if u_log_batch_picking:
            for picking in pickings:
                msg = _(
                    "%s User: %s added picking %s with priority %s to batch %s with priority %s"
                ) % (
                    mode.capitalize(),
                    user_name,
                    picking.name,
                    picking.priority,
                    batch_name,
                    priority,
                )
                _logger.info(msg)
        return diff_priority_pickings

    def get_log_batch_picking_flag(self):
        """Get u_log_batch_picking configuration from warehouse and user name

        Returns:
            Boolean: u_log_batch_picking value
        """
        user = self.env.user
        warehouse = user.get_user_warehouse()
        return warehouse.u_log_batch_picking, user.name

    def reserve_pallet(self, pallet_name, picking=None):
        """
        Reserves a pallet for use in a batch.

        If the batch's picking type's u_reserve_pallet_per_picking flag is
        False, only one pallet can be reserved per batch.

        If the batch's picking type's u_reserve_pallet_per_picking flag is
        True, a different pallet is reserved for each picking in the batch.
        The picking must be passed to this method in this case.

        Pallets are automatically considered unreserved when another pallet is
        reserved or the batch is done.

        Raises a ValidationError if the pallet is already reserved for another
        batch or if a reserving pallets per picking is enabled and a valid
        picking is not provided.
        """
        Picking = self.env["stock.picking"]
        PickingBatch = self.env["stock.picking.batch"]

        self.ensure_one()

        reserve_pallet_per_picking = self.picking_type_id.u_reserve_pallet_per_picking
        if reserve_pallet_per_picking:
            if not picking:
                raise ValidationError(
                    "A picking must be specified if pallets are reserved per picking."
                )
        if reserve_pallet_per_picking and picking and not self.picking_ids & picking:
            raise ValidationError("Picking %s is not in batch %s." % (picking.name, self.name))

        if reserve_pallet_per_picking:
            conflicting_picking = Picking.search(
                [
                    ("u_reserved_pallet", "=", pallet_name),
                    ("state", "not in", ["draft", "cancel", "done"]),
                ]
            )
            if conflicting_picking:
                raise ValidationError(
                    _("This pallet is already being used for picking %s.")
                    % conflicting_picking[0].name
                )
        else:
            conflicting_batch = PickingBatch.search(
                [
                    ("id", "!=", self.id),
                    ("state", "=", "in_progress"),
                    ("u_last_reserved_pallet_name", "=", pallet_name),
                ]
            )
            if conflicting_batch:
                raise ValidationError(
                    _("This pallet is already being used for batch %s.") % conflicting_batch[0].name
                )

        if reserve_pallet_per_picking:
            # The front end will always send only one picking.
            # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
            # but still needs more access rights for the flow
            picking.sudo().write({"u_reserved_pallet": pallet_name})
        else:
            # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
            # but still needs more access rights for the flow
            self.sudo().write({"u_last_reserved_pallet_name": pallet_name})

    def _get_task_grouping_criteria(self):
        """
        Return a function for sorting by picking, package(maybe), product, and
        location. The package is not included if the picking type allows for
        the swapping of packages (`u_allow_swapping_packages`) and picks by
        product (`u_user_scans`)
        """
        batch_pt = self.picking_type_id

        parts = [lambda ml: (ml.picking_id.id,)]

        if not (batch_pt.u_allow_swapping_packages and batch_pt.u_user_scans == "product"):
            parts.append(lambda ml: (ml.package_id.id,))

        parts.append(lambda ml: (ml.location_id.id, ml.product_id.id))

        return lambda ml: tuple(chain(*[part(ml) for part in parts]))

    def get_available_move_lines(self):
        """Get all the move lines from available pickings"""
        self.ensure_one()
        available_pickings = self.picking_ids.filtered(lambda p: p.state == "assigned")

        return available_pickings.get_move_lines_ordered_by()

    def get_next_tasks(
        self,
        skipped_product_ids=None,
        skipped_move_line_ids=None,
        task_grouping_criteria=None,
        limit=1,
    ):
        """
        Get the next not completed tasks of the batch to be done.
        Expect a singleton.

        Note that the criteria for sorting and grouping move lines
        (for the sake of defining tasks) are given by the
        _get_task_grouping_criteria method so it can be specialized
        for different customers. Also note that the
        task_grouping_criteria argument is added to the signature to
        enable dependency injection for the sake of testing.

        Confirmations is a list of dictionaries of the form:
            {'query': 'XXX', 'result': 'XXX'}
        After the user has picked the move lines, should be requested by the
        'query' to scan/type a value that should match with 'result'.
        They are enabled by picking type and should be filled at
        _prepare_task_info(), by default it is not required to confirm anything.
        """
        MoveLine = self.env["stock.move.line"]

        self.ensure_one()

        all_available_mls = self.get_available_move_lines()
        skipped_mls = MoveLine.browse()

        # Filter out skipped move lines
        if skipped_product_ids:
            skipped_mls = all_available_mls.filtered(
                lambda ml: ml.product_id.id in skipped_product_ids
            )
        elif skipped_move_line_ids:
            skipped_mls = all_available_mls.filtered(lambda ml: ml.id in skipped_move_line_ids)
        available_mls = all_available_mls - skipped_mls

        num_tasks_picked = len(available_mls.filtered(lambda ml: ml.qty_done == ml.product_qty))

        incomplete_mls = available_mls.get_lines_incomplete().next_task_sort()
        have_tasks_been_picked = num_tasks_picked > 0

        # Get tasks for movelines that haven't been skipped
        remaining_tasks = self._populate_next_tasks(
            incomplete_mls,
            have_tasks_been_picked,
            task_grouping_criteria=task_grouping_criteria,
            limit=limit,
        )

        # Get tasks for movelines that have been skipped (if allowed)
        incomplete_mls = (
            skipped_mls.filtered(lambda ml: ml.picking_id.picking_type_id.u_return_to_skipped)
            .get_lines_incomplete()
            .next_task_sort()
        )
        # Determine the remaining limit (Need to do a distinct check as False != 0)
        remaining_limit = False
        if type(limit) == int:
            remaining_limit = limit - len(remaining_tasks)
        remaining_tasks += self._populate_next_tasks(
            incomplete_mls,
            have_tasks_been_picked,
            skipped_product_ids=skipped_product_ids,
            skipped_move_line_ids=skipped_move_line_ids,
            task_grouping_criteria=task_grouping_criteria,
            limit=remaining_limit,
        )

        if not remaining_tasks:
            # No viable movelines, create an empty task
            _logger.debug(
                _("Batch '%s': no available move lines for creating " "a task"), self.name
            )
            task = self._populate_next_task(incomplete_mls, task_grouping_criteria)
            task["tasks_picked"] = have_tasks_been_picked
            remaining_tasks.append(task)

        return remaining_tasks

    def get_next_task(
        self, skipped_product_ids=None, skipped_move_line_ids=None, task_grouping_criteria=None
    ):
        """Get the next not completed task of the batch to be done.
        Expect a singleton.
        """
        task = self.get_next_tasks(
            skipped_product_ids=skipped_product_ids,
            skipped_move_line_ids=skipped_move_line_ids,
            task_grouping_criteria=task_grouping_criteria,
            limit=1,
        )[0]
        return task

    def get_completed_tasks(self, task_grouping_criteria=None, limit=False):
        """Get all completed tasks of the batch

        NOTE: These tasks will be in their original order. So if we skip and
        return to a task, the order they are returned in may not be the order
        the tasks were completed in.
        """
        self.ensure_one()

        # Get completed movelines
        all_mls = self.get_available_move_lines()
        completed_mls = (all_mls - all_mls.get_lines_incomplete()).sort_by_key()

        # Generate tasks for the completed move lines
        completed_tasks = self._populate_next_tasks(
            completed_mls, True, task_grouping_criteria=task_grouping_criteria, limit=limit
        )
        return completed_tasks

    def _populate_next_tasks(
        self,
        move_lines,
        have_tasks_been_picked,
        skipped_product_ids=None,
        skipped_move_line_ids=None,
        task_grouping_criteria=None,
        limit=1,
    ):
        """Populate the next tasks according to the given criteria"""
        tasks = []
        while move_lines:
            # Check if there is a move line to give priority to
            priority_ml = move_lines._determine_priority_skipped_moveline(
                skipped_product_ids, skipped_move_line_ids
            )
            task = self._populate_next_task(move_lines, task_grouping_criteria, priority_ml)
            task["tasks_picked"] = have_tasks_been_picked
            tasks.append(task)
            if limit and len(tasks) >= limit:
                break
            move_lines = move_lines.filtered(lambda ml: ml.id not in task["move_line_ids"])
        return tasks

    def _populate_next_task(self, move_lines, task_grouping_criteria, priority_ml=False):
        """Populate the next task from the available move lines and grouping.

        Optionally specify a priority move line to be in the next task.
        """
        task = {"num_tasks_to_pick": 0, "move_line_ids": [], "confirmations": []}
        if not move_lines:
            return task

        if task_grouping_criteria is None:
            task_grouping_criteria = self._get_task_grouping_criteria()

        grouped_mls = move_lines.groupby(task_grouping_criteria)
        _key, task_mls = next(grouped_mls)
        # Iterate through grouped_mls until we find the group with the
        # priority move line in it
        if priority_ml:
            while priority_ml not in task_mls:
                _key, task_mls = next(grouped_mls)
        num_mls = len(task_mls)
        pick_seq = task_mls[0].picking_id.sequence
        _logger.debug(
            _(
                "Batch '%s': creating a task for %s move line%s; "
                "the picking sequence of the first move line is %s"
            ),
            self.name,
            num_mls,
            "" if num_mls == 1 else "s",
            pick_seq if pick_seq is not False else "not determined",
        )

        # NB: adding all the MLs state to the task; this is what
        # ends up in the batch::next response!
        # HERE: this will break in case we cannot guarantee that all
        # the move lines of the task belong to the same picking
        task.update(task_mls._prepare_task_info())

        if task_mls[0].picking_id.picking_type_id.u_user_scans in ["pallet", "package"]:
            # TODO: check pallets of packages if necessary
            task["num_tasks_to_pick"] = len(move_lines.package_id)
            task["move_line_ids"] = move_lines.filtered(
                lambda ml: ml.package_id == task_mls[0].package_id
            ).ids
        else:
            # NB: adding 1 to consider the group removed by next()
            task["num_tasks_to_pick"] = len(list(grouped_mls)) + 1
            task["move_line_ids"] = task_mls.ids

        return task

    def _get_move_lines_to_drop_off(self):
        """Getting all move lines of the batch that are ready to drop off"""
        self.ensure_one()
        return self.picking_ids.move_line_ids.filtered(
            lambda ml: ml.qty_done > 0 and ml.picking_id.state not in ["cancel", "done"]
        )

    def get_next_drop_off(self, item_identity):
        """
        Based on the criteria specified for the batch picking type,
        determines what move lines should be dropped (refer to the
        batch::drop API specs for the format of the returned value).

        Expects an `in_progress` singleton.

        Raises an error in case:
         - not all pickings of the batch have the same picking type;
         - unknown or invalid (e.g. 'all') drop off criterion.
        """
        self.ensure_one()
        assert self.state == "in_progress", "Batch must be in progress to be dropped off"

        all_mls_to_drop = self._get_move_lines_to_drop_off()

        if not len(all_mls_to_drop):
            return {"last": True, "move_line_ids": [], "summary": ""}

        criterion = self.picking_type_id.u_drop_criterion
        func = getattr(all_mls_to_drop, "_get_next_drop_off_" + criterion, None)

        if not func:
            raise ValidationError(
                _("An unexpected drop off criterion is currently configured") + ": '%s'" % criterion
                if criterion
                else ""
            )

        mls_to_drop, summary = func(item_identity)
        last = len(all_mls_to_drop) == len(mls_to_drop)

        return {"last": last, "move_line_ids": mls_to_drop.ids, "summary": summary}

    def drop_off_picked(self, continue_batch, move_line_ids, location_barcode, result_package_name):
        """
        Validate the move lines of the batch (expects a singleton) by moving them
        to the specified location and if continue_batch is not flagged then close the batch.
        Also clears the u_last_reserved_pallet_name flag in the batch as the pallet has been dropped off.

        Note that the work being dropped off always remains in its current picking, and the pending
        work gets placed into any backorder.
        :args:
            - continue_batch: Flag, if True the batch is not closed
            - move_line_ids: model stock.move.line, the move lines to validate
            - location_barcode: String, the destination location barcode for the move lines
            - result_package_name: String, the barcode for the package to be set as result package in move lines
        :returns: the batch in self
        """
        Location = self.env["stock.location"]
        MoveLine = self.env["stock.move.line"]
        Picking = self.env["stock.picking"]
        Package = self.env["stock.quant.package"]
        self.ensure_one()

        if self.state != "in_progress":
            raise ValidationError(_("Wrong batch state: %s.") % self.state)
        dest_loc = None
        if location_barcode:
            dest_loc = Location.get_or_create(location_barcode)

        if move_line_ids:
            completed_move_lines = MoveLine.browse(move_line_ids)
        else:
            completed_move_lines = self._get_move_lines_to_drop_off()

        if completed_move_lines:
            to_update = {}

            if dest_loc:
                to_update["location_dest_id"] = dest_loc.id

            pickings = completed_move_lines.picking_id
            picking_type = pickings.picking_type_id
            picking_type.ensure_one()

            if picking_type.u_scan_parent_package_end:
                if not result_package_name:
                    raise ValidationError(_("Expecting result package on drop off."))

                result_package = Package.get_or_create(result_package_name, create=True)

                if picking_type.u_target_storage_format == "pallet_packages":
                    # TODO: use new package hierarchy
                    to_update["u_result_parent_package_id"] = result_package.id
                elif picking_type.u_target_storage_format == "pallet_products":
                    to_update["result_package_id"] = result_package.id
                else:
                    raise ValidationError(_("Unexpected result package at drop off."))

            if to_update:
                completed_move_lines.write(to_update)

            to_add = Picking.browse()
            picks_todo = Picking.browse()

            for pick, rel_mls in completed_move_lines.groupby("picking_id"):
                # Check if the picking needs to be backordered based on all the move lines
                # in the picking. If something is incomplete then they will be placed into
                # a backorder.
                # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
                # but still needs more access rights for the flow
                backorder = pick.sudo().backorder_move_lines(mls_to_keep=rel_mls)
                # Add the picking to the batch if they are still continuing and it
                # is available to be picked. Else kick it out for auto completion
                # of batches.
                if continue_batch and backorder.state in ("partially_available", "assigned"):
                    to_add |= backorder

                picks_todo |= pick

            picks_todo.write({"u_reserved_pallet": False})

            # If we dropped a package then reset the last package reserved in the batch as we usually
            # ask the user to scan a new pallet once it has been dropped off in a new location
            # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
            # but still needs more access rights for the flow
            self.sudo().u_last_reserved_pallet_name = False

            # Add any created backorders if needed
            if to_add:
                # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
                # but still needs more access rights for the flow
                to_add.sudo().write({"batch_id": self.id})

            with self.statistics() as stats:
                picks_todo.sudo().with_context(tracking_disable=True)._action_done()

            _logger.info(
                "%s action_done in %.2fs, %d queries", picks_todo, stats.elapsed, stats.count
            )
        if not continue_batch:
            # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
            # but still needs more access rights for the flow
            self.sudo().close()

        return self

    def get_single_batch(self, user_id=None):
        """
        Search for a picking batch in progress for the specified user.
        If no user is specified, the current user is considered.

        Raise a ValidationError in case it cannot perform a search
        or if multiple batches are found for the specified user.
        """
        user_id = self._check_user_id(user_id)
        batches = self.get_user_batches(user_id)

        if len(batches) > 1:
            raise ValidationError(
                _("Found %d batches for the user, please contact " "administrator.") % len(batches)
            )

        return batches or None

    def get_user_batches(self, user_id=None):
        """Get all batches for user that are in_progress"""
        if user_id is None:
            user_id = self.env.user.id
        # Search for in progress batches
        batches = self.sudo().search([("user_id", "=", user_id), ("state", "=", "in_progress")])
        return batches

    def _check_user_id(self, user_id):
        """
        If no user_id is passed - set the user to the environment user. If user_id is False, raise an error.
        """
        if user_id is None:
            user_id = self.env.user.id

        if not user_id:
            raise ValidationError(_("Cannot determine the user."))

        return user_id

    @api.model
    def assign_batch(self, picking_type_id, selection_criteria=None):
        """
        Determine all the batches in state 'ready' with pickings
        of the specified picking types then return the one determined
        by the selection criteria method (that should be overridden
        by the relevant customer modules).

        Note that the transition from state 'ready' to 'in_progress'
        is handled by computation of state function.
        """
        if not isinstance(picking_type_id, int):
            raise ValidationError("picking_type_id should be an integer.")
        batches = self.search([("state", "=", "ready"), ("picking_type_id", "=", picking_type_id)])
        batch = False

        if batches:
            batch = self._select_batch_to_assign(batches)
            batch.user_id = self.env.user

        return batch

    def _select_batch_to_assign(self, batches):
        """
        Orders the batches by name and returns the first one.
        """
        assert batches, "Expects a non-empty batches recordset"
        return batches.sorted(key=lambda b: b.name)[0]

    def create_batch(self, picking_type_id, picking_priorities, user_id=None, picking_id=None):
        """
        Create and return a batch for the specified user if pickings
        exist. Return None otherwise. Pickings are filtered based on
        the specified picking priorities (list of int strings, for
        example ['2', '3']).

        If the user already has batches assigned, a ValidationError
        is raised in case of pickings that need to be completed,
        otherwise such batches will be marked as done.
        """
        user_id = self._check_user_id(user_id)
        self._check_user_batch_in_progress(user_id)

        return self._create_batch(
            user_id, picking_type_id, picking_priorities, picking_id=picking_id
        )

    def _check_user_batch_in_progress(self, user_id=None):
        """Check if a user has a batch in progress"""
        batches = self.get_user_batches(user_id=user_id)

        if batches:
            incomplete_picks = batches.picking_ids.filtered(
                lambda pick: pick.state in ["draft", "waiting", "confirmed"]
            )
            picks_txt = ",".join([x.name for x in incomplete_picks])
            raise ValidationError(
                _(
                    "The user already has pickings that need completing - "
                    "please complete those before requesting "
                    "more:\n {}"
                ).format(picks_txt)
            )

    def _create_batch(self, user_id, picking_type_id, picking_priorities=None, picking_id=None, limit=1):
        """
        Create a batch for the specified user by including only the picking(s) with the specified
        picking_type_id and picking priorities (optional) or a specific picking_id.
        The batch will be marked as ephemeral.

        NOTE: by default this function restricts the number of pickings found to 1

        :args:
            - user_id: int
               The user id to assign to the batch
            - picking_type_id: int
               The picking type id to apply to the search
        :kwargs:
            - picking_priorities: list
                List of priority ids to restrict the search of pickings
            - picking_id: int
                If set, the picking id for which to create a batch
            - limit: str
                The number of pickings that the search should return, 1 by default
        :returns:
            stock.picking.batch, the batch created for the picking(s) found or None
        """
        PickingBatch = self.env["stock.picking.batch"]
        Picking = self.env["stock.picking"]

        if picking_id:
            picking = Picking.browse(picking_id)
        else:
            picking = Picking.search_for_pickings(picking_type_id, picking_priorities, limit=limit)

        if not picking:
            return None

        picking_type = picking.picking_type_id

        if picking_type.u_reserve_pallet_per_picking:
            max_reservable_pallets = picking_type.u_max_reservable_pallets
            if len(picking) > max_reservable_pallets:
                raise ValidationError(
                    "Only %d pallets may be reserved at a time." % max_reservable_pallets
                )

        batch = PickingBatch.sudo().create({"user_id": user_id})
        picking.write({"batch_id": batch.id})
        batch.check_same_picking_priority(picking)
        batch.write({"u_ephemeral": True})
        batch.mark_as_todo()

        return batch

    def close(self):
        """Unassign incomplete pickings from batches. In case of a
        non-ephemeral batch then incomplete pickings are moved into a new
        batch.
        """
        for batch in self:
            # Unassign batch_id from incomplete stock pickings on ephemeral batches
            batch.filtered(lambda b: b.u_ephemeral).picking_ids.filtered(
                lambda sp: sp.state not in ("done", "cancel")
            ).write({"batch_id": False, "u_reserved_pallet": False})

            # Assign incomplete pickings to new batch
            _logger.info("Creating continuation batch from %r.", batch.name)
            pickings = (
                batch.filtered(lambda b: not b.u_ephemeral).picking_ids
                .filtered(lambda sp: sp.state not in ("done", "cancel"))
            )
            _logger.info("Picking ids continuation %r", pickings)

            batch._copy_continuation_batch(pickings)

    def _copy_continuation_batch(self, pickings):
        """
        Copy a batch and add the provided pickings.

        The new batch will be named BATCH/nnnnn-XX where XX is a sequence number
        which will be incremented or set to '01'.
        The batch will not be marked as ephemeral.
        In case no pickings exist, return None.
        """
        self.ensure_one()

        if not pickings:
            return None

        new_name = get_next_name(self, "picking.batch")
        batch = self.sudo().copy({"name": new_name, "user_id": None})
        _logger.info("Created continuation batch %r, %s", batch, batch.name)
        if not self.u_original_name:
            batch.write({"u_original_name": self.name})

        pickings.write({"batch_id": batch.id})
        batch.mark_as_todo()

        return batch

    def remove_unfinished_work(self):
        """
        Remove pickings from batch if they are not started
        Backorder half-finished pickings
        """
        Picking = self.env["stock.picking"]

        self.ensure_one()

        if not self.u_ephemeral:
            raise ValidationError(_("Can only remove work from ephemeral batches"))

        pickings_to_remove = Picking.browse()

        for picking in self.picking_ids:
            mls = picking.mapped("move_line_ids")
            started_lines = mls.filtered(lambda ml: ml.qty_done > 0)
            if started_lines:
                mls_to_keep = mls & started_lines
                # Create backorders for incomplete moves and ensure that backorder batch info is
                # also cleared
                # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
                # but still needs more access rights for the flow
                pickings_to_remove |= picking.with_context(lock_batch_state=True).sudo()._backorder_move_lines(mls_to_keep=mls_to_keep)
            else:
                pickings_to_remove |= picking

        pickings_to_remove.with_context(lock_batch_state=True).write(
            {"batch_id": False, "u_reserved_pallet": False}
        )
        # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
        # but still needs more access rights for the flow
        self.sudo()._compute_state()

        return self

    def unpickable_item(
        self,
        reason,
        product_id=None,
        location_id=None,
        package_name=None,
        lot_name=None,
        raise_stock_investigation=True,
        bypass_reassignment=False,
    ):
        """
        Given an unpickable product or package, find the related
        move lines in the current batch, backorder them and refine
        the backorder. Then create a new stock investigation picking
        for the unpickable stock.
        An unpickable product requires at least the location_id and
        optionally the package_id and lot_name.

        TODO: improve looping over pickings to ensure messages are relevant to each picking

        :args:
            - reason: str
                The reason for which the stock is unpickable
        :kwargs:
            - product_id: int
                The product id of unpickable stock
            - location_id: int
                The location id where the unpickable stock lives
            - package_name: str
                The package where the unpickable stock lives
            - lot_name: str
                The lot name of the unpickable stock
            - raise_stock_investigation: Boolean
                Flag to indicate whether to raise a stock investigation picking
            - bypass_reassignment: Boolean
                Flag to indicate whether to reassign stock moves for original pickings
                after raising investigation
            - reason: str
                The reason for which the stock is unpickable
        :returns:
            True if the operation did not fail.
        """
        self.ensure_one()

        Package = self.env["stock.quant.package"]
        Picking = self.env["stock.picking"]
        Location = self.env["stock.location"]
        Product = self.env["product.product"]

        if not self.picking_type_id.u_enable_unpickable_items:
            raise ValidationError(
                _(
                    "This type of operation cannot handle unpickable items. "
                    "Please, contact your team leader to resolve the issue. "
                    "Press back when resolved."
                )
            )

        product = Product.get_or_create(product_id) if product_id else None
        location = Location.get_or_create(location_id) if location_id else None
        package = Package.get_or_create(package_name) if package_name else None
        allow_partial = False
        move_lines = self.get_available_move_lines()

        if product:
            if not location:
                raise ValidationError(
                    _("Missing location parameter for unpickable product %s.") % product.name
                )

            move_lines = move_lines.filtered(
                lambda ml: ml.product_id == product and ml.location_id == location
            )

            msg = _("Unpickable product %s at location %s") % (product.name, location.name)

            if lot_name:
                lot_name = [lot_name] if isinstance(lot_name, str) else lot_name
                move_lines = move_lines.filtered(lambda ml: ml.lot_id.name in lot_name)
                msg += _(" with serial number %s") % lot_name

            if package:
                move_lines = move_lines.filtered(lambda ml: ml.package_id == package)
                msg += _(" in package %s") % package.name
            elif move_lines.package_id:
                raise ValidationError(
                    _("Unpickable product from a package but no package name provided.")
                )

            # at this point we should only have one move_line
            quants = move_lines.get_quants()
            allow_partial = True
        elif package:
            if not location:
                location = package.location_id

            move_lines = move_lines.filtered(
                lambda ml: ml.package_id == package or ml.package_id.parent_id == package
            )
            quants = package._get_contained_quants()
            msg = _("Unpickable package %s at location %s") % (package.name, location.name)
        else:
            raise ValidationError(
                _("Missing required information for unpickable item: product or package.")
            )

        # Filter out the move lines already picked in case under received
        move_lines = move_lines.filtered(lambda ml: ml.qty_done == 0)

        if not move_lines:
            raise ValidationError(
                _("Cannot find move lines todo for unpickable item in this batch.")
            )

        pickings = move_lines.picking_id
        original_picking_ids = {}
        if raise_stock_investigation:
            to_investigate = Picking.browse()
        for picking in pickings:
            if picking.batch_id != self:
                raise ValidationError(_("Move line is not part of the batch."))

            if picking.state in ("cancel", "done"):
                raise ValidationError(
                    _(
                        "Cannot mark a move line as unpickable "
                        "when it is part of a completed Picking."
                    )
                )

            # Post the messages to alert about the unpickable items
            picking.message_post(body=msg)

            original_id = None

            mls_to_backorder = picking.move_line_ids - move_lines
            picking_to_investigate = picking
            if mls_to_backorder:
                # Create a backorder for the affected move lines if there are other move
                # lines not relevant to unpickable move lines. Also, set the backorder as
                # the picking to investigate
                # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
                # but still needs more access rights for the flow
                original_id = picking_to_investigate.id
                picking_to_investigate = picking_to_investigate.sudo()._backorder_move_lines(mls_to_backorder)
            original_picking_ids[picking_to_investigate] = original_id

            if raise_stock_investigation:
                to_investigate |= picking_to_investigate
            else:
                picking_to_investigate.batch_id = False

        if raise_stock_investigation:
            # By default the pick is unreserved
            # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
            # but still needs more access rights for the flow
            to_investigate.with_context(
                lock_batch_state=True, allow_partial=allow_partial
            ).raise_stock_investigation(reason=reason, quants=quants.sudo(), location=location)
            # Trigger refactor here to allow grouping of pickings by move key on confirm. Need to loop
            # over the pickings from the refactored moves as they might be  in a different picking.
            # No unlinking of the empty pickings is done - this relies on the cron to do the clean up
            refactored_moves = (
                to_investigate.exists().move_lines._action_refactor(stage="confirm")
            )
            pickings_to_investigate = refactored_moves.picking_id
            # Some examples to understand the logic below
            # 3 Pickings are generated, we create a stock investigation for a location, but we want to keep
            # processing the original picking, so the 3rd picking will contain a stock move for those products
            # that are not found, take that picking and move the stock moves into the original picking as we
            # want to keep picking those items but from a different location.
            # Otherwise, if not, add the picking to the batch
            if not bypass_reassignment:
                for picking in pickings_to_investigate:
                    moves = picking.move_lines
                    original_picking_id = original_picking_ids.get(picking, None)
                    if (
                        picking.exists()
                        and picking.state == "assigned"
                        and original_picking_id is not None
                        and not picking.picking_type_id.u_post_assign_action
                        # Only if we do not do refactoring because if we do then it's wrong to
                        # move the moves back to the original picking
                    ):
                        # A backorder has been created, but the stock is
                        # available; get rid of the backorder after linking the
                        # move lines to the original picking, so it can be
                        # directly processed
                        picking.move_line_ids.write({"picking_id": original_picking_id})
                        picking.move_lines.write({"picking_id": original_picking_id})
                        picking.unlink()
                    else:
                        # Moves may be part of a new picking after refactor, this should
                        # be added back to the batch
                        other_picking = moves.picking_id.filtered(lambda p: p.state == "assigned")
                        if other_picking:
                            # Need to check as we cannot directly write on empty recordset as original Odoo14
                            # stock batch picking model will raise an error even if recordset is empty
                            other_picking.write({"batch_id": self.id})
            self._remove_unready_picks()
            # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking.batch
            # but still needs more access rights for the flow
            self.sudo()._compute_state()
        return True
