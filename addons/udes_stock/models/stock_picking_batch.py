# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .common import PRIORITIES

import logging

_logger = logging.getLogger(__name__)


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    picking_type_ids = fields.Many2many(
        'stock.picking.type', string="Operation Types",
        compute='_compute_picking_type', store=True, index=True,
    )
    scheduled_date = fields.Datetime(
        string="Scheduled Date", compute='_compute_scheduled_date',
        store=True, index=True,
    )
    u_ephemeral = fields.Boolean(
        string="Ephemeral",
        help="Ephemeral batches are unassigned if the user logs out"
    )
    priority = fields.Selection(
        selection=PRIORITIES, string="Priority", store=True, index=True,
        readonly=True, compute='_compute_priority',
        help="Priority of a batch is the maximum priority of its pickings."
    )
    state = fields.Selection(
        selection = [
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('ready', 'Ready'),
            ('in_progress', 'Running'),
            ('done', 'Done'),
            ('cancel', 'Cancelled')
        ],
        compute='_compute_state',
        store=True,
    )

    u_location_category_id = fields.Many2one(
        comodel_name='stock.location.category',
        compute='_compute_location_category',
        string='Location Category',
        help="Used to know which pickers have the right equipment to pick it. "
             "In case multiple location categories are found in the picking it "
             "will be empty.",
        readonly=True,
        store=True,
    )

    @api.depends('picking_ids',
                 'picking_ids.u_location_category_id')
    @api.one
    def _compute_location_category(self):
        """ Compute location category from picking_ids"""
        if self.picking_ids:
            categories = self.picking_ids.mapped('u_location_category_id')
            self.u_location_category_id = \
                categories if len(categories) == 1 else False

    @api.multi
    def confirm_picking(self):
        """Overwrite method confirm picking to raise error if not in draft and
           rollback to draft on error in action_assign.
        """
        if any(batch.state != 'draft' for batch in self):
            raise ValidationError(_(
                'Batch (%s) is not in state draft can not perform '
                'confirm_picking') % ','.join(
                    b.name for b in self if b.state != 'draft')
            )

        pickings_todo = self.mapped('picking_ids')
        self.write({'state': 'waiting'})  # Get it out of draft

        try:
            p = pickings_todo.action_assign()
            self._compute_state()

            return p
        except:
            self.write({'state': 'draft'})
            raise

    @api.multi
    @api.depends('picking_ids', 'picking_ids.picking_type_id')
    def _compute_picking_type(self):
        for batch in self:
            batch.picking_type_ids = batch.picking_ids.mapped('picking_type_id')

    @api.multi
    @api.depends('picking_ids', 'picking_ids.scheduled_date')
    def _compute_scheduled_date(self):
        for batch in self:
            batch.scheduled_date = min(
                batch.picking_ids.mapped('scheduled_date') or
                [fields.Datetime.now()]
            )

    @api.multi
    @api.depends('picking_ids.priority')
    def _compute_priority(self):
        for batch in self:
            new_priority = False
            if batch.mapped('picking_ids'):
                priorities = batch.mapped('picking_ids.priority')
                new_priority = max(priorities)
            if new_priority != batch.priority:
                batch.priority = new_priority

    @api.multi
    @api.constrains('user_id')
    def _compute_state(self):
        """ Compute the state of a batch post confirm
            waiting     : At least some picks are not ready
            ready       : All picks are in ready state (assigned)
            in_progress : All picks are ready and a user has been assigned
            done        : All picks are complete (in state done or cancel)

            the other two states are draft and cancel are manual
            to transitions from or to the respective state.
        """
        if self.env.context.get('lock_batch_state'):
            # State is locked so don't do anything
            return

        for batch in self:
            if batch.state in ['draft', 'done', 'cancel']:
                # Can not do anything with them don't bother trying
                continue

            ready_picks, other_picks = \
                batch._calculate_pick_groups(batch.picking_ids)

            if batch.picking_ids and (ready_picks or other_picks):
                # State-specific transitions
                if batch.state == 'waiting':
                    if other_picks:
                        # Not all picks are ready
                        pass
                    elif batch.user_id:
                        batch.state = 'in_progress'
                    else:
                        batch.state = 'ready'
                elif batch.state == 'ready':
                    if other_picks:
                        batch.state = 'waiting'
                    elif batch.user_id:
                        batch.state = 'in_progress'
                elif batch.state == 'in_progress':
                    if ready_picks and not other_picks and not batch.user_id:
                        # User is removed
                        batch.state = 'ready'
                    elif other_picks:
                        # Not really a transition but a bit of batch pick managemnet
                        # which has to be delt with
                        # We shouldn't have these check if we can make them ready
                        # otherwise remove them
                        batch._remove_unready_picks()
                else:
                    _logger.error(_("Ignoring unexpected batch state: %s")
                                  % batch.state)
            else:
                # Valid for all states; this accounts for all
                # pickings being complete, canceled or all pickings
                # get removed for some reason.
                # The last two can happen in any state
                batch.state = 'done'

    def _calculate_pick_groups(self, picks):
        """Collect picks into groups based on state - complete picks are ignored
           Groups are
                ready    : pick.state is assigned
                other    : pick.state is in any other state than the ones above
        """
        Picking = self.env['stock.picking']

        ready_picks = Picking.browse()
        other_picks = Picking.browse()

        for pick in picks:
            if pick.state == 'assigned':
                ready_picks |= pick
            elif pick.state in ['done', 'cancel']:
                continue
            else:
                other_picks |= pick

        return ready_picks, other_picks

    @api.multi
    def _remove_unready_picks(self, picks=None):
        if picks is None:
            picks = self.mapped('picking_ids')

        # first lets double check there are not ready
        not_ready_lam = lambda pick: pick.state in \
            ['draft', 'waiting', 'confirmed']
        not_ready = picks.filtered(not_ready_lam)

        if not_ready:
            confirmed_not_ready = not_ready.filtered(
                lambda pick: pick.state == 'confirmed')

            if confirmed_not_ready:
                # Attempt to make confirmed picks ready
                confirmed_not_ready.action_assign()

            # Filter again as we are possibly calling action_assign which
            # could make some of the previous not ready picks to now be ready
            not_ready.filtered(not_ready_lam).write({'batch_id': False})
            self._compute_state()

    def _get_task_grouping_criteria(self):
        """
        Return a function for sorting by package, product, and
        location.
        """
        return lambda ml: (ml.picking_id.id,
                           ml.package_id.id,
                           ml.product_id.id,
                           ml.location_id.id)

    def get_next_task(self, skipped_product_ids=None,
                            task_grouping_criteria=None):
        """
        Get the next not completed task of the batch to be done.
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
        self.ensure_one()

        available_mls = self.get_available_move_lines()

        if skipped_product_ids is not None:
            available_mls = available_mls.filtered(
                lambda ml: ml.product_id.id not in skipped_product_ids)

        num_tasks_picked = len(available_mls.filtered(
            lambda ml: ml.qty_done == ml.product_qty))
        task = {'tasks_picked': num_tasks_picked > 0,
                'num_tasks_to_pick': 0,
                'move_line_ids': [],
                'confirmations': [],
                }
        todo_mls = available_mls.get_lines_todo() \
                                .sort_by_location_product()

        if todo_mls:
            if task_grouping_criteria is None:
                task_grouping_criteria = self._get_task_grouping_criteria()

            grouped_mls = todo_mls.groupby(task_grouping_criteria)
            _key, task_mls = next(grouped_mls)
            num_mls = len(task_mls)
            pick_seq = task_mls[0].picking_id.sequence
            _logger.debug(_("Batch '%s': creating a task for %s move line%s; "
                            "the picking sequence of the first move line is %s"),
                            self.name,
                            num_mls,
                            '' if num_mls == 1 else 's',
                            pick_seq if pick_seq is not False else "not determined")

            # NB: adding all the MLs state to the task; this is what
            # ends up in the batch::next response!
            # HERE: this will break in case we cannot guarantee that all
            # the move lines of the task belong to the same picking
            task.update(task_mls._prepare_task_info())

            if task_mls[0].picking_id.picking_type_id.u_user_scans == 'product':
                # NB: adding 1 to consider the group removed by next()
                task['num_tasks_to_pick'] = len(list(grouped_mls)) + 1
                task['move_line_ids'] = task_mls.ids
            else:
                # TODO: check pallets of packages if necessary
                task['num_tasks_to_pick'] = len(todo_mls.mapped('package_id'))
                task['move_line_ids'] = todo_mls.filtered(
                    lambda ml: ml.package_id == task_mls[0].package_id).ids
        else:
            _logger.debug(_("Batch '%s': no available move lines for creating "
                            "a task"), self.name)

        return task

    def _check_user_id(self, user_id):
        if user_id is None:
            user_id = self.env.user.id

        if not user_id:
            raise ValidationError(_("Cannot determine the user."))

        return user_id

    @api.multi
    def get_single_batch(self, user_id=None):
        """
        Search for a picking batch in progress for the specified user.
        If no user is specified, the current user is considered.

        Raise a ValidationError in case it cannot perform a search
        or if multiple batches are found for the specified user.
        """
        PickingBatch = self.env['stock.picking.batch']

        user_id = self._check_user_id(user_id)
        batches = PickingBatch.search([('user_id', '=', user_id),
                                       ('state', '=', 'in_progress')])
        batch = None

        if batches:
            if len(batches) > 1:
                raise ValidationError(
                    _("Found %d batches for the user, please contact "
                      "administrator.") % len(batches))

            batch = batches

        return batch

    def _prepare_info(self, allowed_picking_states):
        pickings = self.picking_ids

        if allowed_picking_states:
            pickings = pickings.filtered(
                lambda x: x.state in allowed_picking_states)

        return {'id': self.id,
                'name': self.name,
                'state': self.state,
                'u_ephemeral': self.u_ephemeral,
                'picking_ids': pickings.get_info(),
                'result_package_names': pickings.get_result_packages_names()}

    def get_info(self, allowed_picking_states):
        """
        Return list of dictionaries containing information about
        all batches.
        """
        return [batch._prepare_info(allowed_picking_states)
                for batch in self]

    def _select_batch_to_assign(self, batches):
        """
        Orders the batches by name and returns the first one.
        """
        assert batches, "Expects a non-empty batches recordset"
        return batches.sorted(key=lambda b: b.name)[0]

    @api.model
    def assign_batch(self, picking_type_id, selection_criteria=None):
        """
        Determine all the batches in state 'ready' with pickings
        of the specified picking types then return the one determined
        by the selection criteria method (that should be overriden
        by the relevant customer modules).

        Note that the transition from state 'ready' to 'in_progress'
        is handled by computation of state function.
        """
        batches = self.search([('state', '=', 'ready')]) \
                      .filtered(lambda b: all([pt.id == picking_type_id
                                               for pt in b.picking_type_ids]))

        if batches:
            batch = self._select_batch_to_assign(batches)
            batch.user_id = self.env.user

            return batch

    @api.multi
    def create_batch(self, picking_type_id, picking_priorities, user_id=None, picking_id=None):
        """
        Creeate and return a batch for the specified user if pickings
        exist. Return None otherwise. Pickings are filtered based on
        the specified picking priorities (list of int strings, for
        example ['2', '3']).

        If the user already has batches assigned, a ValidationError
        is raised in case of pickings that need to be completed,
        otherwise such batches will be marked as done.
        """
        user_id = self._check_user_id(user_id)
        self._check_user_batch_in_progress(user_id)

        return self._create_batch(user_id, picking_type_id, picking_priorities, picking_id=picking_id)

    def _create_batch(self, user_id, picking_type_id, picking_priorities=None, picking_id=None):
        """
        Create a batch for the specified user by including only
        those pickings with the specified picking_type_id and picking
        priorities (optional).
        The batch will be marked as ephemeral.
        In case no pickings exist, return None.
        """
        PickingBatch = self.env['stock.picking.batch']
        Picking = self.env['stock.picking']

        if picking_id:
            picking = Picking.browse(picking_id)
        else:
            picking = Picking.search_for_pickings(picking_type_id, picking_priorities)

        if not picking:
            return None

        batch = PickingBatch.sudo().create({'user_id': user_id})
        picking.write({'batch_id': batch.id})
        batch.write({'u_ephemeral': True})
        batch.confirm_picking()

        return batch

    def add_extra_pickings(self, picking_type_id):
        """ Get the next available picking and add it to the current users batch """
        Picking = self.env['stock.picking']

        picking_priorities = self.get_batch_priority_group()
        pickings = Picking.search_for_pickings(picking_type_id, picking_priorities)

        if not pickings:
            raise ValidationError(_("No more work to do."))

        if not self.u_ephemeral:
            raise ValidationError(_("Can only add work to ephemeral batches"))

        pickings.write({'batch_id': self.id})
        return True

    def _check_user_batch_in_progress(self, user_id=None):
        """Check if a user has a batch in progress"""
        batches = self.get_user_batches(user_id=user_id)

        if batches:
            incomplete_picks = batches.picking_ids.filtered(
                lambda pick: pick.state in ['draft', 'waiting', 'confirmed']
            )
            picks_txt = ','.join([x.name for x in incomplete_picks])
            raise ValidationError(
                _("The user already has pickings that need completing - "
                  "please complete those before requesting "
                  "more:\n {}").format(picks_txt)
            )

    def drop_off_picked(self, continue_batch, move_line_ids, location_barcode,
                        result_package_name):
        """
        Validate the move lines of the batch (expects a singleton)
        by moving them to the specified location.

        In case continue_batch is flagged, unassign the batch.
        """
        self.ensure_one()

        if self.state != 'in_progress':
            raise ValidationError(_("Wrong batch state: %s.") % self.state)

        Location = self.env['stock.location']
        MoveLine = self.env['stock.move.line']
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']
        dest_loc = None

        if location_barcode:
            dest_loc = Location.get_location(location_barcode)

        if move_line_ids:
            completed_move_lines = MoveLine.browse(move_line_ids)
        else:
            completed_move_lines = self._get_move_lines_to_drop_off()

        if completed_move_lines:
            to_update = {}

            if dest_loc:
                to_update['location_dest_id'] = dest_loc.id

            pickings = completed_move_lines.mapped('picking_id')
            picking_type = pickings.mapped('picking_type_id')
            picking_type.ensure_one()

            if picking_type.u_scan_parent_package_end:
                if not result_package_name:
                    raise ValidationError(
                        _('Expecting result package on drop off.')
                    )

                result_package = Package.get_package(result_package_name,
                                                     create=True)

                if picking_type.u_target_storage_format == 'pallet_packages':
                    to_update['u_result_parent_package_id'] = result_package.id
                elif picking_type.u_target_storage_format == 'pallet_products':
                    to_update['result_package_id'] = result_package.id
                else:
                    raise ValidationError(
                        _('Unnexpected result package at drop off.')
                    )

            if to_update:
                completed_move_lines.write(to_update)

            to_add = Picking.browse()
            picks_todo = Picking.browse()

            for pick in pickings:
                pick_todo = pick
                pick_mls = completed_move_lines.filtered(
                    lambda x: x.picking_id == pick)

                if pick._requires_backorder(pick_mls):
                    pick_todo = pick._backorder_movelines(pick_mls)
                    to_add |= pick_todo

                picks_todo |= pick_todo

            # Add backorders to the batch
            to_add.write({'batch_id': self.id})

            with self.statistics() as stats:
                picks_todo.sudo().with_context(tracking_disable=True).action_done()

            _logger.info("%s action_done in %.2fs, %d queries",
                         picks_todo, stats.elapsed, stats.count)

        if not continue_batch:
            self.unassign()

        return self

    @api.model
    def get_drop_off_instructions(self, criterion):
        """
        Returns a string indicating instructions about what the
        user has to scan before requesting the move lines for
        drop off.

        Raises an error if the instruction method for the
        specified criterion does not exist.
        """
        func = getattr(self, '_get_drop_off_instructions_' + criterion, None)

        if not func:
            raise ValidationError(
                _("An unexpected drop off criterion is currently configured")
                + ": '%s'" % criterion if criterion else "")

        return func()

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
        assert self.state == 'in_progress', \
               "Batch must be in progress to be dropped off"

        all_mls_to_drop = self._get_move_lines_to_drop_off()

        if not len(all_mls_to_drop):
            return {'last': True,
                    'move_line_ids': [],
                    'summary': ""}

        picking_type = self.picking_type_ids

        if len(picking_type) > 1:
            raise ValidationError(
                _("The batch unexpectedly has pickings of different types"))

        criterion = picking_type.u_drop_criterion
        func = getattr(self, '_get_next_drop_off_' + criterion, None)

        if not func:
            raise ValidationError(
                _("An unexpected drop off criterion is currently configured")
                + ": '%s'" % criterion if criterion else "")

        mls_to_drop, summary = func(item_identity, all_mls_to_drop)
        last = len(all_mls_to_drop) == len(mls_to_drop)

        return {'last': last,
                'move_line_ids': mls_to_drop.mapped('id'),
                'summary': summary}

    def _get_move_lines_to_drop_off(self):
        self.ensure_one()
        return self.picking_ids \
                   .mapped('move_line_ids') \
                   .filtered(lambda ml:
                        ml.qty_done > 0
                        and ml.picking_id.state not in ['cancel', 'done'])

    def _get_next_drop_off_all(self, item_identity, mls_to_drop):
        raise ValidationError(
            _("The 'all' drop off criterion should not be invoked"))

    def _get_drop_off_instructions_all(self):
        raise ValidationError(
            _("The 'all' drop off instruction should not be invoked"))

    def _get_next_drop_off_by_products(self, item_identity, mls_to_drop):
        mls = mls_to_drop.filtered(
            lambda ml: ml.product_id.barcode == item_identity)
        summary = mls._drop_off_criterion_summary()

        return mls, summary

    def _get_drop_off_instructions_by_products(self):
        return _("Please scan the product that you want to drop off")

    def _get_next_drop_off_by_orders(self, item_identity, mls_to_drop):
        mls = mls_to_drop.filtered(
            lambda ml: ml.picking_id.origin == item_identity)
        summary = mls._drop_off_criterion_summary()

        return mls, summary

    def _get_drop_off_instructions_by_orders(self):
        return _("Please enter the order of the items that you want to drop off")

    def is_valid_location_dest_id(self, location_ref):
        """
        Whether the specified location (via ID, name or barcode)
        is a valid putaway location for the relevant pickings of
        the batch.
        Expects a singleton instance.

        Returns a boolean indicating the validity check outcome.
        """
        self.ensure_one()

        Location = self.env['stock.location']
        location = None

        try:
            location = Location.get_location(location_ref)
        except:
            return False

        done_pickings = self.picking_ids.filtered(
            lambda p: p.state == 'assigned')
        done_move_lines = done_pickings.get_move_lines_done()
        all_done_pickings = done_move_lines.mapped('picking_id')

        return all([pick.is_valid_location_dest_id(location=location)
                    for pick in all_done_pickings])

    def _check_unpickable_item(self):
        """ Checks if all the picking types of the batch are allowed to handle
            unpickable items. If one of them does not, it raises an error.
        """
        if not all(self.picking_type_ids.mapped('u_enable_unpickable_items')):
            raise ValidationError(
                _('This type of operation cannot handle unpickable items. '
                  'Please, contact your team leader to resolve the issue. '
                  'Press back when resolved.')
            )


    def unpickable_item(self,
                        reason,
                        product_id=None,
                        location_id=None,
                        package_name=None,
                        lot_name=None,
                        raise_stock_investigation=True):
        """
        Given an unpickable product or package, find the related
        move lines in the current batch, backorder them and refine
        the backorder (by default it is canceled).
        Then create a new stock investigation picking for the
        unpickable stock.
        If the picking was the last one of the batch, the batch is
        set as done.

        An unpickable product requires at least the location_id and
        optionally the package_id and lot_name.
        """
        self.ensure_one()

        Package = self.env['stock.quant.package']
        Location = self.env['stock.location']
        Product = self.env['product.product']

        self._check_unpickable_item()

        product = Product.get_product(product_id) if product_id else None
        location = Location.get_location(location_id) if location_id else None
        package = Package.get_package(package_name) if package_name else None
        allow_partial = False
        move_lines = self.get_available_move_lines()

        if product:
            if not location:
                raise ValidationError(
                    _('Missing location parameter for unpickable product %s.') %
                    product.name)

            move_lines = move_lines.filtered(lambda ml: ml.product_id == product and
                                             ml.location_id == location)

            msg = _('Unpickable product %s at location %s') % (product.name, location.name)

            if lot_name:
                move_lines = move_lines.filtered(lambda ml: ml.lot_id.name == lot_name)
                msg += _(' with serial number %s') % lot_name

            if package:
                move_lines = move_lines.filtered(lambda ml: ml.package_id == package)
                msg += _(' in package %s') % package.name
            elif move_lines.mapped('package_id'):
                raise ValidationError(
                    _('Unpickable product from a package but no package name provided.'))

            # at this point we should only have one move_line
            quants = move_lines.get_quants()
            allow_partial = True
        elif package:
            if not location:
                location = package.location_id

            move_lines = move_lines.filtered(lambda ml: ml.package_id == package)
            quants = package._get_contained_quants()
            msg = _('Unpickable package %s at location %s') % (package.name, location.name)
        else:
            raise ValidationError(
                _('Missing required information for unpickable item: product or package.'))

        if not move_lines:
            raise ValidationError(
                _('Cannot find move lines todo for unpickable item '
                  'in this batch.'))

        # at this point we should have only one picking_id
        picking = move_lines.mapped('picking_id')
        picking.message_post(body=msg)

        if picking.batch_id != self:
            raise ValidationError(_('Move line is not part of the batch.'))

        if picking.state in ['cancel', 'done']:
            raise ValidationError(_('Cannot mark a move line as unpickable '
                                    'when it is part of a completed Picking.'))

        original_picking_id = None

        if len(picking.move_line_ids - move_lines):
            # Create a backorder for the affected move lines if
            # there are move lines that are not affected
            original_picking_id = picking.id
            picking = picking._backorder_movelines(move_lines)

        moves = picking.move_lines
        if raise_stock_investigation:
            # By default the pick is unreserved
            picking.with_context(
                lock_batch_state=True,
                allow_partial=allow_partial,
            ).raise_stock_inv(
                reason=reason,
                quants=quants,
                location=location,
            )

            if picking.exists() \
                    and picking.state == 'assigned' \
                    and original_picking_id is not None\
                    and not picking.picking_type_id.u_post_assign_action:
                # A backorder has been created, but the stock is
                # available; get rid of the backorder after linking the
                # move lines to the original picking, so it can be
                # directly processed
                picking.move_line_ids.write({'picking_id': original_picking_id})
                picking.move_lines.write({'picking_id': original_picking_id})
                picking.unlink()
            else:
                # Moves may be part of a new picking after refactor, this should
                # be added back to the batch
                moves.mapped('picking_id')\
                    .filtered(lambda p: p.state == 'assigned')\
                    .write({'batch_id': self.id})
            self._compute_state()

        else:
            picking.batch_id = False

        return True

    def get_available_move_lines(self):
        """ Get all the move lines from available pickings
        """
        self.ensure_one()
        available_pickings = self.picking_ids.filtered(
            lambda p: p.state == 'assigned')

        return available_pickings.mapped('move_line_ids')

    def get_user_batches(self, user_id=None):
        """ Get all batches for user
        """
        if user_id is None:
            user_id = self.env.user.id
        # Search for in progress batches
        batches = self.sudo().search([('user_id', '=', user_id),
                                      ('state', '=', 'in_progress')])
        return batches

    def unassign_user_batches(self):
        """ Get batches for user and unassign them
        """
        # Get user batches
        self.get_user_batches().unassign()

    def unassign(self):
        """ Unassign user from batches, in case of an ephemeral batch then
        also unassign incomplete pickings from the batch
        """
        # Unassign user from batch
        self.sudo().write({'user_id': False})

        # Unassign batch_id from incomplete stock pickings on ephemeral batches
        self.filtered(lambda b: b.u_ephemeral)\
            .mapped('picking_ids')\
            .filtered(lambda sp: sp.state not in ('done', 'cancel'))\
            .write({'batch_id': False})

    def remove_unfinished_work(self):
        """
        Remove pickings from batch if they are not started
        Backorder half-finished pickings
        """
        Picking = self.env['stock.picking']

        self.ensure_one()

        if not self.u_ephemeral:
            raise ValidationError(
                _("Can only remove work from ephemeral batches"))

        pickings_to_remove = Picking.browse()
        pickings_to_add = Picking.browse()

        for picking in self.picking_ids:
            started_lines = picking.mapped('move_line_ids').filtered(
                lambda x: x.qty_done > 0)
            if started_lines:
                # backorder incomplete moves
                if picking._requires_backorder(started_lines):
                    pickings_to_add |= picking.with_context(
                        lock_batch_state=True)._backorder_movelines(started_lines)
                    pickings_to_remove |= picking
            else:
                pickings_to_remove |= picking

        pickings_to_remove.with_context(
            lock_batch_state=True).write({'batch_id': False})
        pickings_to_add.with_context(
            lock_batch_state=True).write({'batch_id': self.id})
        self._compute_state()

        return self

    def get_batch_priority_group(self):
        """ Get priority group for this batch based on the pickings' priorities
        Returns list of IDs
        """
        Picking = self.env['stock.picking']

        if not self.picking_ids:
            raise ValidationError(_("Batch without pickings cannot have a priority group"))

        picking_priority = self.picking_ids[0].priority
        priority_groups = Picking.get_priorities()
        for priority_group in priority_groups:
            priority_ids = [priority['id'] for priority in priority_group['priorities']]
            if picking_priority in priority_ids:
                return priority_ids
        return None

    def mark_as_todo(self):
        """Changes state from draft to waiting.

        This is done without calling action assign.
        """
        _logger.info("User %r has marked %r as todo.",
                     self.env.uid, self)
        not_draft = self.filtered(lambda b: b.state != 'draft')
        if not_draft:
            raise UserError(
                _('Only draft batches may be marked as "todo": %s') % not_draft.ids
            )
        self.write({'state': 'waiting'})
        self._compute_state()

        return
