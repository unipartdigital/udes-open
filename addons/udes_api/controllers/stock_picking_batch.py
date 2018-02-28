# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from .main import UdesApi


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

        return batch.get_info() if batch else {}

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

        return batch.get_info() if batch else {}
