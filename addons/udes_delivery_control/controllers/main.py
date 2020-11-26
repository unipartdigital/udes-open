from odoo import http, _
from odoo.http import request
from odoo.addons.udes_stock.controllers.main import UdesApi
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class PickingApi(UdesApi):
    def _get_picking_info(self, pickings, fields_to_fetch=None):
        """Return a list with the information of each picking in pickings.

        @param pickings
                Odoo stock.picking object
        @param (optional) fields_to_fetch
                List of fields
        Returns:
            list: Returns list of picking dictionary
        """
        info = ["id", "name", "origin", "state", "u_is_backload", "u_is_unload"]
        if not fields_to_fetch:
            fields_to_fetch = info
        return [picking.read(fields_to_fetch)[0] for picking in pickings]

    @http.route("/api/delivery-control/stock-picking/", type="json", methods=["GET"], auth="user")
    def get_pickings_delivery_control(self, fields_to_fetch=None, **kwargs):
        """ Search for pickings by various criteria and return an
            array of stock.picking objects that match a given criteria.

            @param fields_to_fetch: Array (string)
                Subset of the default returned fields to return.
        """
        Picking = request.env["stock.picking"]
        pickings = Picking.get_pickings(**kwargs)
        return self._get_picking_info(pickings, fields_to_fetch)

    @http.route(
        "/api/delivery-control/stock-picking/<int:ident>",
        type="json",
        methods=["POST"],
        auth="user",
    )
    def confirm_picking(self, ident, **kwargs):
        """ Update and confirm picking """
        Picking = request.env["stock.picking"]
        picking = Picking.browse(ident)

        if not picking.exists():
            raise ValidationError(_("Cannot find stock.picking with id %s") % ident)

        # Set User
        kwargs["u_user_id"] = request.env.uid
        with picking.statistics() as stats:
            picking.write(kwargs)
            picking.button_validate()
        _logger.info(
            "Updating picking(s) (user %s) in %.2fs, %d queries, %s",
            request.env.uid,
            stats.elapsed,
            stats.count,
            picking.ids,
        )

        return True
