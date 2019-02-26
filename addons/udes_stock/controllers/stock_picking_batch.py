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
    if len(info) != 1:
        raise AssertionError("Expected exactly one batch")

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
        In case one is found, return a JSON object with:
         - the ID, state, and the name of the batch ('id', 'state',
           'name' strings);
         - the list of pickings in assigned state ('picking_ids'
           array of stock.picking objects);
         - the result packages ('result_package_names' array).

        In case the user has no batch, return an empty object.

        Raises a ValidationError in case multiple batches are found
        for the current user.
        """
        PickingBatch = request.env['stock.picking.batch']
        batch = PickingBatch.get_single_batch()

        return _get_single_batch_info(batch,
                                      allowed_picking_states=['assigned'])

    @http.route('/api/stock-picking-batch/check-user-batches',
                type='json', methods=['GET'], auth='user')
    def check_user_batches(self):
        """
        Whether the user has any assigned batch.
        """
        PickingBatch = request.env['stock.picking.batch']
        batches = PickingBatch.get_user_batches()

        return True if batches else False

    @http.route('/api/stock-picking-batch/<ident>/next',
                type='json', methods=['GET'], auth='user')
    def get_next_task(self, ident, skipped_product_ids=None):
        """
        Returns the next pick task from the picking batch in
        progress for the current user.
        A task will include one or more move lines from
        different pickings.

        Raises a ValidationError if the specified batch does
        not exist.

        In case the batch is not completed, returns an object
        containing information regarding the next task:
        picking_id and package/product information.
        Returns an empty object otherwise.
        """
        batch = _get_batch(request.env, ident)

        return batch.get_next_task(skipped_product_ids=skipped_product_ids)

    @http.route('/api/stock-picking-batch/assign/',
                type='json', methods=['POST'], auth='user')
    def assign_batch_to_user(self, picking_type_id):
        """
        Assign a batch of the specified picking type to the current
        user (see API specs).
        """
        PickingBatch = request.env['stock.picking.batch']
        batch = PickingBatch.assign_batch(picking_type_id)

        if batch:
            assert batch.state == 'in_progress', \
                   "Assigned batches should be 'in_progress'"

            return _get_single_batch_info(batch,
                                          allowed_picking_states=['assigned'])
        else:
            return {}

    @http.route('/api/stock-picking-batch/<ident>/unassign',
                type='json', methods=['POST'], auth='user')
    def unassign_batch(self, ident):
        """
        Unassign the specified batch (see API specs).

        Raise a ValidationError in case:
         - the specified batch does not exist;
         - the specified batch is not `in_progress`;
         - the specified batch is not assigned to the current user.
        """
        batch = _get_batch(request.env, ident)

        if batch.state == 'in_progress':
            if batch.user_id.id != request.env.user.id:
                raise ValidationError(
                    _("The specified batch is not assigned to you."))

            batch.unassign()

        return True

    @http.route('/api/stock-picking-batch/',
                type='json', methods=['POST'], auth='user')
    def create_batch_for_user(self,
                              picking_type_id,
                              picking_priorities=None):
        """
        Create a batch for the user if pickings are available.

        If a batch is created, return a JSON object with the ID of
        the batch ('id' string) and the list of pickings ('picking_ids'
        array of stock.picking objects), otherwise return an empty
        object.

        Raises a ValidationError in case a batch already exists for
        the current user.

        @param picking_type_id - Id of the picking type for the pickings
            which will be used to create the batch.
        @param picking_priorities - (optional) List of priorities to
            search for the pickings
        """
        PickingBatch = request.env['stock.picking.batch']
        batch = PickingBatch.create_batch(picking_type_id, picking_priorities)

        return _get_single_batch_info(batch)

    @http.route('/api/stock-picking-batch/<ident>',
                type='json', methods=['POST'], auth='user')
    def update_batch(self, ident,
                     continue_batch,
                     move_line_ids,
                     location_barcode=None,
                     result_package=None):
        """
        Update the specified batch by inspecting its move lines
        and setting the destination to the location with the
        provided `location_barcode`. Refer to the API specs for
        more details.

        In case all pickings are completed, the batch will be
        marked as 'done' if `continue_batch` is flagged (defaults
        to false).
        """
        batch = _get_batch(request.env, ident)
        updated_batch = batch.drop_off_picked(continue_batch,
                                              move_line_ids,
                                              location_barcode,
                                              result_package)

        return _get_single_batch_info(updated_batch)

    @http.route('/api/stock-picking-batch/<ident>/drop',
                type='json', methods=['GET'], auth='user')
    def get_next_drop_off(self, ident, identity):
        """
        Determines what move lines from the batch the user should
        drop off, based on the picked item specified by its
        `identity`. Returns an object containing the move lines
        and other metadata for guiding the user during the drop off
        workflow (refer to the API specs for more details).

        Raises a ValidationError in case the specified batch does
        not exist or if it's not in progress.
        """
        batch = _get_batch(request.env, ident)

        if batch.state != 'in_progress':
            raise ValidationError(_("The specified batch is not in progress."))

        return batch.get_next_drop_off(identity)

    @http.route('/api/stock-picking-batch/<ident>/is-valid-dest-location',
                type='json', methods=['GET'], auth='user')
    def validate_drop_off_location(self, ident,
                                   location_id=None,
                                   location_name=None,
                                   location_barcode=None):
        """
        Validates the specified drop off location for the given
        batch by checking if the location exists and, if so, whether
        it's a valid location for putaway for the relevant pickings.
        The location can be either a location ID, name or barcode;
        the method expects one of such entries to be specified.

        Raises a ValidationError in case the batch doesn't exist.

        Returns a boolean indicating the outcome of the validation.
        """
        batch = _get_batch(request.env, ident)

        if not any([location_id, location_name, location_barcode]):
            raise ValidationError(_('You need to specify a location id, name, '
                                    'or barcode.'))

        location_ref = None

        if location_id is not None:
            try:
                location_ref = int(location_id)
            except ValueError:
                raise ValidationError(_('You need to provide a valid id for '
                                        'the location.'))
        else:
            location_ref = location_name or location_barcode

        outcome = batch.is_valid_location_dest_id(location_ref)
        assert any([outcome is x for x in [False, True]]), \
            "Unexpected outcome from the drop off location validation"

        return outcome

    @http.route('/api/stock-picking-batch/<ident>/unpickable',
                type='json', methods=['POST'], auth='user')
    def unpickable_item(self, ident, reason, product_id=None, location_id=None,
                        package_name=None):
        """
        Creates a Stock Investigation for the specified move_line_id for the
        given batch.  If necessary a backorder will be created.
        """
        # Do not raise stock investigation when package does not fit,
        # just remove it from the batch
        raise_stock_investigation = (reason not in (
            "package does not fit"
        ))

        batch = _get_batch(request.env, ident)
        return batch.unpickable_item(
            reason=reason,
            product_id=product_id,
            location_id=location_id,
            package_name=package_name,
            raise_stock_investigation=raise_stock_investigation
        )

    @http.route('/api/stock-picking-batch/<ident>/add-extra-pickings',
                type='json', methods=['POST'], auth='user')
    def add_extra_pickings(self, ident, picking_type_id):
        """
        If pickings are available and the user has single in batch
        in progress - add the next available picking to this batch

        Raises a ValidationError if no pickings are available

        @param picking_type_id - Id of the picking type for the pickings
            which will be used to create the batch.
        """
        batch = _get_batch(request.env, ident)
        batch.add_extra_pickings(picking_type_id)

        return _get_single_batch_info(batch)

    @http.route('/api/stock-picking-batch/<ident>/remove-unfinished-work',
                type='json', methods=['POST'], auth='user')
    def remove_unfinished_work(self, ident):
        """
        Remove pickings from batch if they are not started.
        Returned the metadata of the batch, by only including
        the 'assigned' pickings.

        Backorder half-finished pickings
        """
        batch = _get_batch(request.env, ident)
        updated_batch = batch.remove_unfinished_work()

        return _get_single_batch_info(updated_batch,
                                      allowed_picking_states=['assigned'])
