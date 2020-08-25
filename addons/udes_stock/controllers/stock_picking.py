# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

from .main import UdesApi
import logging

_logger = logging.getLogger(__name__)


class PickingApi(UdesApi):

    @http.route('/api/stock-picking/',
                type='json', methods=['GET'], auth='user')
    def get_pickings(self, fields_to_fetch=None, **kwargs):
        """ Search for pickings by various criteria and return an
            array of stock.picking objects that match a given criteria.

            @param fields_to_fetch: Array (string)
                Subset of the default returned fields to return.
        """
        Picking = request.env['stock.picking']

        pickings = Picking.get_pickings(**kwargs)

        return pickings.get_info(fields_to_fetch=fields_to_fetch)

    @http.route('/api/stock-picking/',
                type='json', methods=['POST'], auth='user')
    def create_picking(self, **kwargs):
        """ Old create_internal_transfer
        """
        Picking = request.env['stock.picking']
        picking = Picking.create_picking(**kwargs)

        return picking.get_info()[0]

    @http.route('/api/stock-picking/<ident>',
                type='json', methods=['POST'], auth='user')
    def update_picking(self, ident, **kwargs):
        """ Old force_validate/validate_operation
        """
        Picking = request.env['stock.picking']
        picking = Picking.browse(int(ident))

        if not picking.exists():
            raise ValidationError(_('Cannot find stock.picking with id %s') % ident)

        with picking.statistics() as stats:
            picking.update_picking(**kwargs)
        _logger.info("Updating picking(s) (user %s) in %.2fs, %d queries, %s",
                     request.env.uid, stats.elapsed, stats.count, picking.ids)


        # If refactoring deletes our original picking, info may not be available
        # in case this has happened return true
        if picking.exists():
            return picking.get_info()[0]
        return True

    @http.route('/api/stock-picking/<ident>/is_compatible_package/<package_name>',
                type='json', methods=['GET'], auth='user')
    def is_compatible_package(self, ident, package_name):
        """ Check if the package name is compatible with the
            picking with id <ident>, i.e., the package name has not been
            used before, only has been used in the same picking and
            it is not in use at stock.
        """
        Picking = request.env['stock.picking']
        picking = Picking.browse(int(ident))

        if not picking.exists():
            raise ValidationError(_('Cannot find stock.picking with id %s') % ident)

        return picking.is_compatible_package(package_name)

    @http.route('/api/stock-picking/<ident>/batch-it/',
                type='json', methods=['POST'], auth='user')
    def batch_to_user(self, ident):
        """ Create a batch assigned to the current user for the picking if the
            auto batch flag is set at the picking type.
            If the picking is already in a batch raise an error if the user
            of the batch is different or no user.
        """
        Picking = request.env['stock.picking']
        picking = Picking.browse(int(ident))
        res = None

        if picking.picking_type_id.u_auto_batch_pallet:
            picking.batch_to_user(request.env.user)
            res = picking.batch_id.get_info(None)[0]

        return res

    @http.route('/api/stock-picking/<int:ident>/warn_picking_precondition',
                type='json', methods=['GET'], auth='user')
    def warn_picking_precondition(self, ident):
        """ Check if picking does not fulfill a precondition.
            Returns a warning string if it doesn't, False otherwise.
        """
        Picking = request.env['stock.picking']

        picking = Picking.browse(ident)
        return picking.action_warn_picking_precondition()
