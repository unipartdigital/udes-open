from odoo import models, fields, api
from odoo.exceptions import ValidationError
from.common import PRIORITIES
from itertools import chain


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    u_last_reserved_pallet_name = fields.Char(
        string="Last Pallet Used",
        index=True,
        help="Barcode of the last pallet used for this batch. "
        "If the batch is in progress, indicates the pallet currently in "
        "use.",
    )
    u_ephemeral = fields.Boolean(
        string="Ephemeral", help="Ephemeral batches are unassigned if the user logs out"
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

    @api.depends("picking_ids.priority")
    def _compute_priority(self):
        for batch in self:
            # Get the old priority of the batch
            old_priority = False
            if not isinstance(batch.id, models.NewId):
                old_priority = batch.read(["priority"])[0]["priority"]
            if batch.picking_ids:
                priorities = batch.mapped("picking_ids.priority")
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
            location = Location.get_location(location_ref)
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
        picking_type.ensure_one()
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
        """ Get priority group for this batch based on the pickings' priorities
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

        reserve_pallet_per_picking = self.picking_type_ids.u_reserve_pallet_per_picking
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
            picking.write({"u_reserved_pallet": pallet_name})
        else:
            self.write({"u_last_reserved_pallet_name": pallet_name})

    def _get_task_grouping_criteria(self):
        """
        Return a function for sorting by picking, package(maybe), product, and
        location. The package is not included if the picking type allows for
        the swapping of packages (`u_allow_swapping_packages`) and picks by
        product (`u_user_scans`)
        """
        batch_pt = self.mapped("picking_ids.picking_type_id")
        batch_pt.ensure_one()

        parts = [lambda ml: (ml.picking_id.id,)]

        if not (batch_pt.u_allow_swapping_packages and batch_pt.u_user_scans == "product"):
            parts.append(lambda ml: (ml.package_id.id,))

        parts.append(lambda ml: (ml.location_id.id, ml.product_id.id))

        return lambda ml: tuple(chain(*[part(ml) for part in parts]))

    def get_available_move_lines(self):
        """ Get all the move lines from available pickings
        """
        self.ensure_one()
        available_pickings = self.picking_ids.filtered(lambda p: p.state == "assigned")

        return available_pickings.move_line_ids

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

        todo_mls = available_mls.get_lines_todo().sort_by_location_product()
        have_tasks_been_picked = num_tasks_picked > 0

        # Get tasks for movelines that haven't been skipped
        remaining_tasks = self._populate_next_tasks(
            todo_mls,
            have_tasks_been_picked,
            task_grouping_criteria=task_grouping_criteria,
            limit=limit,
        )

        # Get tasks for movelines that have been skipped (if allowed)
        todo_mls = (
            skipped_mls.filtered(lambda ml: ml.picking_id.picking_type_id.u_return_to_skipped)
            .get_lines_todo()
            .sort_by_location_product()
        )
        # Determine the remaining limit (Need to do a distninct check as False != 0)
        remaining_limit = False
        if type(limit) == int:
            remaining_limit = limit - len(remaining_tasks)
        remaining_tasks += self._populate_next_tasks(
            todo_mls,
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
            task = self._populate_next_task(todo_mls, task_grouping_criteria)
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
        completed_mls = (all_mls - all_mls.get_lines_todo()).sort_by_location_product()

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
            priority_ml = False
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
            task["num_tasks_to_pick"] = len(move_lines.mapped("package_id"))
            task["move_line_ids"] = move_lines.filtered(
                lambda ml: ml.package_id == task_mls[0].package_id
            ).ids
        else:
            # NB: adding 1 to consider the group removed by next()
            task["num_tasks_to_pick"] = len(list(grouped_mls)) + 1
            task["move_line_ids"] = task_mls.ids

        return task
