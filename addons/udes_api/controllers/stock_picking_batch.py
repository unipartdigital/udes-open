# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request

from .main import UdesApi


#
## Helpers
#

def _get_single_batch_info(batch, allowed_picking_states=None):
    if not batch:
        return {}

    info = batch.get_info(allowed_picking_states)
    assert len(info) == 1, "expected exactly one batch"

    return info[0]


def _get_batch(env, batch_id_txt):
    PickingBatch = env['stock.picking.batch']
    batch_id = None

    try:
        batch_id = int(batch_id_txt)
    except ValueError:
        raise ValidationError(_('You need to provide a valid id for the '
                                'batch.'))

    batch = PickingBatch.browse(batch_id)

    if not batch.exists():
        raise ValidationError(_('The specified batch does not exist.'))

    return batch


#
## PickingBatchApi endpoints
#

class PickingBatchApi(UdesApi):

    @http.route('/api/stock-picking-batch/',
                type='json', methods=['GET'], auth='user')
    def get_users_batch(self):
        """
        Search for a picking batch in progress for the current user.
        If no batch is found, but pickings exist, create a new batch.

        If a batch is determined, return a JSON object with the ID of
        the batch ('id' string) and the list of pickings ('picking_ids'
        array of stock.picking objects), otherwise return an empty
        object.

        Raises a ValidationError in case multiple batches are found
        for the current user.
        """
        PickingBatch = request.env['stock.picking.batch']
        batch = PickingBatch.get_single_batch()

        return _get_single_batch_info(batch,
                                      allowed_picking_states=['assigned'])

    @http.route('/api/stock-picking-batch/',
                type='json', methods=['POST'], auth='user')
    def create_batch_for_user(self,
                              picking_priorities=None,
                              max_locations=None):
        """
        Create a batch for the user if pickings are available.

        If a batch is created, return a JSON object with the ID of
        the batch ('id' string) and the list of pickings ('picking_ids'
        array of stock.picking objects), otherwise return an empty
        object.

        Raises a ValidationError in case a batch already exists for
        the current user.

        @param picking_priorities - (optional) List of priorities to
            search for the pickings
        @param max_locations - (optional) Max number of locations to
            pick from (not used)
        """
        PickingBatch = request.env['stock.picking.batch']
        batch = PickingBatch.create_batch(picking_priorities)

        return _get_single_batch_info(batch)

    @http.route('/api/stock-picking-batch/<ident>',
                type='json', methods=['POST'], auth='user')
    def update_batch(self, ident,
                     location_barcode=None,
                     continue_wave=False):
        """
        Update the specified batch by inspecting its move lines
        and setting the destination to the location with the
        provided `location_barcode`.

        In case all pickings are completed, the batch will be
        marked as 'done' if `continue_wave` is flagged (defaults
        to false).
        """
        batch = _get_batch(request.env, ident)
        updated_batch = batch.drop_off_picked(continue_wave, location_barcode)

        return _get_single_batch_info(updated_batch)

    @http.route('/api/stock-picking-batch/<ident>/is-valid-dest-location/<location>',
                type='json', methods=['GET'], auth='user')
    def validate_drop_off_location(self, ident, location):
        """
        Validates the specified drop off location for the given
        batch by checking if the location exists and, if so, whether
        it's a valid location for putaway for the relevant pickings.
        The location can be either a location ID, name or barcode.

        Raises a ValidationError in case the batch doesn't exist.

        Returns a boolean indicating the outcome of the validation.
        """
        batch = _get_batch(request.env, ident)
        outcome = batch.is_valid_location_dest_id(location)
        assert any([outcome is x for x in [False, True]]), \
            "Unexpected outcome from the drop off location validation"

        return outcome
