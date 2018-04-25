# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

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

        if not batches:
            batch = self._create_batch(user_id)
        else:
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
                'picking_ids': pickings.get_info()}

    def get_info(self, allowed_picking_states):
        """
        Return list of dictionaries containing information about
        all batches.
        """
        return [batch._prepare_info(allowed_picking_states)
                for batch in self]

    @api.multi
    def create_batch(self, picking_priorities, user_id=None):
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
        self._check_batches(user_id)

        return self._create_batch(user_id, picking_priorities)

    def _create_batch(self, user_id, picking_priorities=None):
        """
        Create a batch for the specified user, by including only
        those pickings with the specified picking priorities
        (optional).
        In case no pickings exist, return None.
        """
        Picking = self.env['stock.picking']
        PickingBatch = self.env['stock.picking.batch']
        Users = self.env['res.users']

        warehouse = Users.get_user_warehouse()
        picking_type_id = warehouse.pick_type_id
        search_domain = []

        if picking_priorities is not None:
            search_domain.append(('priority', 'in', picking_priorities))

        search_domain.extend([('picking_type_id', '=', picking_type_id.id),
                              ('state', '=', 'assigned'),
                              ('batch_id', '=', False)])

        picking = Picking.search(search_domain,
                                 order='priority desc, scheduled_date, id',
                                 limit=1)

        if not picking:
            return None

        batch = PickingBatch.create({'user_id': user_id})
        picking.batch_id = batch.id
        batch.write({'state': 'in_progress'})

        return batch

    def _check_batches(self, user_id):
        """
        In case there is a batch for the specified user, run
        through its pickings and raise a ValidationError if any
        non-draft picking is incomplete, otherwise mark the batch
        as done.
        """
        Picking = self.env['stock.picking']
        PickingBatch = self.env['stock.picking.batch']

        batches = PickingBatch.search([('user_id', '=', user_id),
                                       ('state', '=', 'in_progress')])

        if batches:
            draft_picks = Picking.browse()
            incomplete_picks = Picking.browse()

            for pick in batches.mapped('picking_ids'):
                if pick.state == 'draft':
                    draft_picks += pick
                elif pick.state not in ['done', 'cancel']:
                    incomplete_picks += pick

            if draft_picks:
                draft_picks.write({'batch_id': None})

            if incomplete_picks:
                picks_txt = ','.join([x.name for x in incomplete_picks])
                raise ValidationError(
                    _("The user already has pickings that need completing - "
                      "please complete those before requesting "
                      "more:\n {}".format(picks_txt)))

            # all the picks in the waves are finished
            batches.done()

    def drop_off_picked(self, continue_wave, location_barcode):
        """
        Validate the move lines of the batch (expects a singleton)
        by moving them to the specified location.

        In case continue_wave is flagged, mark the batch as
        'done' if appropriate.
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

        if not dest_loc and completed_move_lines:
            raise ValidationError(_("Drop off lane not found."))

        if dest_loc and completed_move_lines:
            completed_move_lines.write({'location_dest_id': dest_loc.id})
            pickings = completed_move_lines.mapped('picking_id')

            for pick in pickings:
                pick.update_picking(validate=True, create_backorder=True)

                # @todo: (ale) decide whether or not to trigger backorder
                # operations in inverse order based on the number of
                # move lines (prior art below for reference):
                #
                # pick_move_lines = completed_move_lines.filtered(
                #     lambda x: x.picking_id == pick)
                # if len(pick.move_line_ids) == len(pick_move_lines):
                #     pick.update_picking(validate=True, create_backorder=True)
                # else:
                #     # @todo: (ale) backorder operations in inverse order

        incomplete_picks = self.picking_ids.filtered(
            lambda x: x.state not in ['done', 'cancel'])
        all_done = not incomplete_picks

        if not continue_wave:
            incomplete_picks.write({'batch_id': False})
            all_done = True

        if all_done:
            # there's nothing else to be picked...
            self.done()

        return self

    def is_valid_location_dest_id(self, location_ref):
        """
        Whether the specified location (via ID, name or barcode)
        is a valid putaway location for the all the relavant
        pickings of the batch.
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

    def unpickable_item(self, move_line_id, reason, picking_type_id=None):
        """
        Given a valid move_line_id create a new picking of type picking_type_id
        picking for it. If it is the last move_line_id of the wave,
        the wave is set as done.

        The move_line_id is valid if it is in the current wave (self)
        and its picking is not done or cancel.
        """

        self.ensure_one()

        ResUsers = self.env['res.users']
        StockMoveLine = self.env['stock.move.line']
        Picking = self.env['stock.picking']
        Group = self.env['procurement.group']

        move_line = StockMoveLine.browse(move_line_id)
        if not move_line.exists():
            # We need to check these here lest we throw exceptions
            # when getting picking_id, package_id etc
            raise ValidationError(_('Cannot find the operation'))

        picking = move_line.picking_id
        package = move_line.package_id
        location = move_line.location_id

        if picking_type_id is None:
            picking_type_id = ResUsers.get_user_warehouse().int_type_id.id
        if picking.batch_id != self:
            raise ValidationError(_('Move line is not part of the batch.'))
        if picking.state in ['cancel', 'done']:
            raise ValidationError(_('Cannot mark a move line as unpickable '
                                    'when it is part of a completed Picking.'))

        if package:
            # This move line is part of a package.  Get all quants that are
            # also on this package as well as all other move lines in the
            # package as they will have been affected as well.
            quants = package._get_contained_quants()
            move_lines = picking.move_line_ids.get_package_move_lines(package)
            msg = 'Unpickable package %s at location %s'

            picking.message_post(body=_(msg) % (package.name, location.name))

        else:
            raise ValidationError("Not Implemented")

        if len(picking.move_line_ids - move_lines):
            # Create a backorder for the affected move lines if there are
            # move lines that are not affected
            picking = picking._create_backorder(move_lines)

        # Remove the pick from the batch, and refine it
        picking.batch_id = False
        # By default the pick is cancelled
        picking._refine_picking(reason)

        group = Group.get_group(group_identifier=reason,
                                 create=True)

        # create new "investigation pick"
        Picking.create_picking(quant_ids=quants.mapped('id'),
                               location_id=location.id,
                               picking_type_id=picking_type_id,
                               group_id=group.id)

        # If the batch does not contain any remaining picking to do, it can
        # be set as done
        remaining_pickings = self.picking_ids.filtered(
            lambda x: x.state in ['assigned']
        )
        if not remaining_pickings.exists():
            self.state = 'done'

        return True

    def get_tasks(self, state=None):
        """ Generate all the tasks not completed of the batch in self.
            Optionally filter them by the state: done or not_done.
        """
        self.ensure_one()

        available_pickings = self.picking_ids.filtered(lambda p: p.state == 'assigned')
        mls = available_pickings.mapped('move_line_ids')

        return mls.generate_tasks(state=state)

    def get_next_task(self):
        """ Gets the next not completed task of the batch to be done
        """
        self.ensure_one()

        tasks = self.get_tasks(state='not_done')


        return tasks[0] if tasks else {}

    def validate_task(self,
                      transaction_id,
                      **kwargs):
        """ TODO: better name?


        """
        MoveLine = self.env['stock.move.line']

        self.ensure_one()
        next_task = self.get_next_task()
        if next_task['transaction_id'] != transaction_id:
            raise ValidationError(
                _('Transaction does not match, your batch might have changed. '
                  'Please contact team leader.')
            )

        mls = MoveLine.browse(transaction_id['move_line_ids'])
        pickings = mls.mapped('picking_id')

        if len(picking) == 1:
            pickings.update_picking(**kwargs)
        else:
            # group mls by picking_id
            # for picking, mls in XXX:
            #   compute product_ids for current picking
            #   picking.update_picking
            raise ValidationError('Not implemented yet')

        return True
