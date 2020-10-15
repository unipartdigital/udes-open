# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError

from .main import UdesApi


class StockMoveLineApi(UdesApi):
    @http.route(
        "/api/stock-move-line/suggested-locations", type="json", methods=["POST"], auth="user"
    )
    def suggested_locations(self, move_line_ids):
        """
        Search suggested locations - refer to the API specs for details.
        """
        MoveLine = request.env["stock.move.line"]

        if not move_line_ids:
            raise ValidationError(_("Must specify the 'move_line_ids' entry"))

        response = []
        locations = None
        empty_locations = None
        mls = MoveLine.browse(move_line_ids)

        for pick in mls.mapped("picking_id"):
            pick_mls = mls.filtered(lambda ml: ml.picking_id == pick)
            pick_locs = pick.get_suggested_locations(pick_mls)
            locations = pick_locs if locations is None else locations & pick_locs

            if pick.picking_type_id.u_drop_location_constraint == "enforce_with_empty":
                pick_empty_locs = pick.get_empty_locations()
                empty_locations = (
                    pick_empty_locs
                    if empty_locations is None
                    else empty_locations & pick_empty_locs
                )

        if locations:
            response.append({"title": "", "locations": locations.get_info()})

            if empty_locations:
                # Ensure we don't have duplicates in the two recordsets
                empty_locations = empty_locations - locations

        if empty_locations:
            response.append({"title": "empty", "locations": empty_locations.get_info()})

        return response

    @http.route("/api/stock-move-line/", type="json", methods=["GET"], auth="user")
    def get_move_lines(
        self,
        picking_id,
        product_barcode,
        package_name=None,
        lot_name=None,
        only_done=False,
        fetch_fields=None,
    ):
        """Fetches move lines on the given picking
            which match the criteria provided
        Args:
            picking_id: int
                ID of the picking

            product_barcode: string
                Barcode of product on target move line/s

            package_name: string (optional)
                Name/Barcode of the package on target move line/s

            lot_name: string (optional)
                Name of the lot on target move line/s

            only_done: boolean (optional)
                Flag to use only complete lines

            fetch_fields: list[string] (optional)
                The fields which should be returned if not set
                                                    all are returned

        Errors:
            If no picking is found for picking_id
            If no move lines match

        Returns:
            list of dicts from calling get_info on the matched move lines

        """

        Picking = request.env["stock.picking"]
        picking = Picking.browse(picking_id)

        if not picking:
            raise UserError(_("Picking with id = %s not found") % picking_id)

        if only_done:
            mls = picking.get_move_lines_done()
        else:
            mls = picking.move_line_ids

        filter_lamb = lambda ml: ml.product_id.barcode == product_barcode

        if package_name:
            filter_lamb = lambda ml, other=filter_lamb: (
                ml.result_package_id.name == package_name
                or ml.u_result_parent_package_id.name == package_name
            ) and other(ml)

        if lot_name:
            filter_lamb = lambda ml, other=filter_lamb: (
                ml.lot_name == lot_name or ml.lot_id.name
            ) and other(ml)

        matched_mls = mls.filtered(filter_lamb)

        if not matched_mls:
            fields = [
                ("picking_id", picking_id),
                ("product_barcode", product_barcode),
                ("package_name", package_name),
                ("lot_name", lot_name),
            ]
            citeria = ["%s=%s" % (n, v) for n, v in fields if v is not None]
            raise UserError(_("No move line found matching citeria: %s") % ", ".join(citeria))
        return matched_mls.get_info(fetch_fields)
