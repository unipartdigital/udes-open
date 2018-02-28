# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    @api.multi
    def get_single_batch(self, user_id=None):
        """
        Search for a picking batch in progress for the specified user.
        If no user is specified, the current user is considered.
        If no batch is found, but pickings exist, create a new batch.

        If a batch is determined, return it, otherwise return None.

        Raises a ValidationError in case multiple batches are found
        for the current user.
        """
        PickingBatch = self.env['stock.picking.batch']

        if user_id is None:
            user_id or self.env.user.id

        batches = PickingBatch.search(
            [('user_id', '=', user_id),
             ('state', '=', 'in_progress')])
        batch = None

        if not batches:
            batch = self._create_batch(user_id)
        else:
            if len(batches) > 1:
                raise ValidationError(
                    _("Expected single picking batch, found %d batches")
                    % len(batches))

            batch = batches[0]

        return batch

    def _get_single_batch_info(self, batch, allowed_picking_states):
        filtered_pickings = batch.picking_ids.filtered(
            lambda x: x.state in allowed_picking_states)

        return {'id': self.id,
                'picking_ids': filtered_pickings.get_info()}

    def get_info(self, allowed_picking_states=None):
        """
        Return list of dictionaries containing information about
        all batches.
        """
        if allowed_picking_states is None:
            allowed_picking_states = ['assigned']

        return [self._get_single_batch_info(batch, allowed_picking_states)
                for batch in self]

    @api.multi
    def create_batch(self, user_id=None):
        """
        Creeate and return a batch for the specified user if pickings
        exist. Return None otherwise.
        """
        user_id = user_id or self.env.user.id
        self._check_batches(user_id)

        return self._create_batch(user_id)

    def _create_batch(self, user_id):
        Picking = self.env['stock.picking']
        PickingBatch = self.env['stock.picking.batch']
        Users = self.env['res.users']

        warehouse = Users.get_user_warehouse()
        picking_type_id = warehouse.pick_type_id
        search_domain = [('picking_type_id', '=', picking_type_id.id),
                         ('state', '=', 'assigned'),
                         ('batch_id', '=', False)]
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
