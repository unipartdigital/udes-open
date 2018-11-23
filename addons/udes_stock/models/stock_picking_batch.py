# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
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
    u_ephemeral = fields.Boolean(string="Ephemeral",
                                  help="Ephemeral batches are unassigned if the user logs out")

    priority = fields.Selection(
        selection=PRIORITIES, string="Priority", store=True, index=True,
        readonly=True, compute='_compute_priority',
        help="Priority of a batch is the maximum priority of its pickings."
    )

    state = fields.Selection(
        selection_add=[
            ('waiting', 'Waiting'),
            ('ready', 'Ready'),
        ],
        compute='_compute_state',
        store=True,
    )

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
            res = pickings_todo.action_assign()
        except:
            # On an error rollback to draft
            self.write({'state': 'draft'})
            # Then reraise the error
            raise
        return res

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
            to tranistions from or to the respective state.
        """
        for batch in self:

            if batch.state in ['draft', 'done', 'cancel']:
                # Can not do anything with them don't bother trying
                continue

            ready_picks, other_picks = \
                self._calculate_pick_groups(batch.picking_ids)

            if not batch.picking_ids or not (ready_picks or other_picks):
                # This accounts for all pickings being complete, canceled or
                # all pickings get removed for some reason.
                # The last two can happen in any state
                batch.state = 'done'

            # Attempt transitions based on state
            elif batch.state == 'waiting':
                batch._from_waiting_transitions(other_picks)

            elif batch.state == 'ready':
                batch._from_ready_transitions(other_picks)

            elif batch.state == 'in_progress':
                batch._from_in_progress_transitions(ready_picks, other_picks)

            else:
                # How did we get here?
                # Let do nothing to be safe!
                continue

    def _from_in_progress_transitions(self, ready_picks=None, other_picks=None):
        """ Transition from in_progress to another state"""
        self.ensure_one()

        # Make sure we have the pick groups
        if ready_picks is None or other_picks is None:
            ready_picks, other_picks = \
                self._calculate_pick_groups(self.picking_ids)

        # This transitions should be handled already in _compute_state
        # but as a guard against it being called else where by someone
        # lets add it in here as well
        if not ready_picks and not other_picks:
            # All picks are complete so we're done
            self.state = 'done'
            return True

        elif ready_picks and not other_picks and not self.user_id:
            # User is removed lets go back to being ready
            self.state = 'ready'
            return True

        # None really a transition but a bit of batch pick managemnet
        # which has to be delt with
        elif other_picks:
            # We shouldn't have these check if we can make them ready
            # otherwise remove them
            return self._remove_unready_picks()

    def _from_waiting_transitions(self, other_picks=None):
        """ Transition from waiting to another state"""
        self.ensure_one()

        # Make sure we have the pick groups
        if other_picks is None:
            _, other_picks = self._calculate_pick_groups(self.picking_ids)

        # the check that there is picks should be done already in
        # _compute_state but as a guard against it being called else
        # where by someone lets add it in here as well
        if self.picking_ids and other_picks:
            # Not all picks are ready don't transition
            return False

        if self.user_id:
            self.state = 'in_progress'
        else:
            self.state = 'ready'
        return True

    def _from_ready_transitions(self, other_picks=None):
        """ Transition from ready to another state"""
        self.ensure_one()

        # Make sure we have the pick groups
        if other_picks is None:
            _, other_picks = self._calculate_pick_groups(self.picking_ids)

        if other_picks:
            self.state = 'waiting'
            return True

        elif self.user_id:
            self.state = 'in_progress'
            return True

        return False

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

        # first lets double check there not ready
        not_ready_lam = lambda pick: pick.state in \
            ['draft', 'waiting', 'confirmed']
        not_ready = picks.filtered(not_ready_lam)

        if not_ready:
            confirmed_not_ready = not_ready.filtered(
                lambda pick: pick.state == 'confirmed')
            if confirmed_not_ready:
                confirmed_not_ready.action_assign()

            not_ready.filtered(not_ready_lam).write({'batch_id': False})
            return self._compute_state()

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
                'move_line_ids': []}
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
        If no batch is found, but pickings exist, create a new batch.

        If a batch is determined, return it, otherwise return None.

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
                'picking_ids': pickings.get_info(),
                'result_package_names': pickings.get_result_packages_names()}

    def get_info(self, allowed_picking_states):
        """
        Return list of dictionaries containing information about
        all batches.
        """
        return [batch._prepare_info(allowed_picking_states)
                for batch in self]

    @api.multi
    def create_batch(self, picking_type_id, picking_priorities, user_id=None):
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

        return self._create_batch(user_id, picking_type_id, picking_priorities)

    def _create_batch(self, user_id, picking_type_id, picking_priorities=None):
        """
        Create a batch for the specified user by including only
        those pickings with the specified picking_type_id and picking
        priorities (optional).
        In case no pickings exist, return None.
        """
        Picking = self.env['stock.picking']
        PickingBatch = self.env['stock.picking.batch']

        search_domain = []

        if picking_priorities is not None:
            search_domain.append(('priority', 'in', picking_priorities))

        search_domain.extend([('picking_type_id', '=', picking_type_id),
                              ('state', '=', 'assigned'),
                              ('batch_id', '=', False)])

        # Note: order should be determined by stock.picking._order
        picking = Picking.search(search_domain, limit=1)

        if not picking:
            return None

        batch = PickingBatch.create({'user_id': user_id})
        picking.batch_id = batch.id
        batch.write({'u_ephemeral': True})
        batch.confirm_picking()

        return batch

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

    def drop_off_picked(self, continue_batch, location_barcode):
        """
        Validate the move lines of the batch (expects a singleton)
        by moving them to the specified location.

        In case continue_batch is flagged, unassign the batch
        """
        self.ensure_one()

        if self.state != 'in_progress':
            raise ValidationError(_("Wrong batch state: %s.") % self.state)

        Location = self.env['stock.location']
        dest_loc = None

        if location_barcode:
            dest_loc = Location.get_location(location_barcode)

        completed_move_lines = self.picking_ids.mapped('move_line_ids').filtered(
            lambda x: x.qty_done > 0
                      and x.picking_id.state not in ['cancel', 'done'])

        if dest_loc and completed_move_lines:
            completed_move_lines.write({'location_dest_id': dest_loc.id})

        if completed_move_lines:
            pickings = completed_move_lines.mapped('picking_id')

            for pick in pickings:
                pick_todo = pick
                pick_mls = completed_move_lines.filtered(lambda x: x.picking_id == pick)

                if pick._requires_backorder(pick_mls):
                    pick_todo = pick._backorder_movelines(pick_mls)

                # at this point pick_todo should contain only mls done
                pick.update_picking(validate=True)
        if not continue_batch:
            self.unassign()

        return self

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

    def unpickable_item(self,
                        reason,
                        product_id=None,
                        location_id=None,
                        package_name=None,
                        picking_type_id=None,
                        lot_name=None,
                        raise_stock_investigation=True):
        """
        Given an unpickable product or package, find the related
        move lines in the current batch, backorder them and refine
        the backorder (by default it is canceled).
        Then create a new picking of type picking_type_id for the
        unpickable stock.
        If the picking was the last one of the batch, the batch is
        set as done.

        An unpickable product requires at least the location_id and
        optionally the package_id and lot_name.
        """
        self.ensure_one()

        ResUsers = self.env['res.users']
        Picking = self.env['stock.picking']
        Group = self.env['procurement.group']
        Package = self.env['stock.quant.package']
        Location = self.env['stock.location']
        Product = self.env['product.product']

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
                location=package.location_id

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

        if picking_type_id is None:
            picking_type_id = ResUsers.get_user_warehouse().int_type_id.id

        if picking.state in ['cancel', 'done']:
            raise ValidationError(_('Cannot mark a move line as unpickable '
                                    'when it is part of a completed Picking.'))

        original_picking_id = None

        if len(picking.move_line_ids - move_lines):
            # Create a backorder for the affected move lines if
            # there are move lines that are not affected
            original_picking_id = picking.id
            picking = picking._backorder_movelines(move_lines)

        if raise_stock_investigation:
            # By default the pick is unreserved
            picking._refine_picking(reason)

            group = Group.get_group(group_identifier=reason,
                                    create=True)

            # create new "investigation pick"
            Picking.with_context(allow_partial=allow_partial)\
                .create_picking(quant_ids=quants.mapped('id'),
                                location_id=location.id,
                                picking_type_id=picking_type_id,
                                group_id=group.id)

            # Try to re-assing the picking after, by creating the
            # investigation, we've reserved the problematic stock
            picking.action_assign()

            if picking.state != 'assigned':
                # Remove the picking from the batch as it cannot be
                # processed for lack of stock; we do so to be able
                # to terminate the batch and let the user create a
                # new batch for himself
                picking.batch_id = False
            elif original_picking_id is not None:
                # A backorder has been created, but the stock is
                # available; get rid of the backorder after linking the
                # move lines to the original picking, so it can be
                # directly processed
                picking.move_line_ids.write({'picking_id': original_picking_id})
                picking.move_lines.write({'picking_id': original_picking_id})
                picking.unlink()

        else:
            picking.batch_id = False

        # If the batch does not contain any remaining picking to do,
        # it can be set as done
        remaining_pickings = self.picking_ids.filtered(
            lambda x: x.state in ['assigned'])

        if not remaining_pickings.exists():
            self.state = 'done'

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
        batches = self.search([('user_id', '=', user_id),
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
        self.write({'user_id': False})

        # Unassign batch_id from incomplete stock pickings on ephemeral batches
        self.filtered(lambda b: b.u_ephemeral)\
            .mapped('picking_ids')\
            .filtered(lambda sp: sp.state not in ('done', 'cancel'))\
            .write({'batch_id': False})
