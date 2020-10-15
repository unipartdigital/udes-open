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
        self, picking_id, product_barcodes, package_names=None, lot_names=None, only_done=False,
    ):
        """Fetches move lines on the given picking which match the criteria provided.

        Note: any combination of the values provided will form a match.

        Args:
            picking_id: int
                ID of the picking

            product_barcodes: list[string]
                Barcodes of product on target move line/s

            package_names: list[string] (optional)
                Names of the package on target move line/s

            lot_names: list[string] (optional)
                Names of the lot on target move line/s

            only_done: boolean (optional)
                Flag to use only complete lines

        Errors:
            If no picking is found for picking_id
            If no move lines match

        Returns:
            list of dicts from calling get_info on the matched move lines

        """

        Picking = request.env["stock.picking"]
        Product = request.env["product.product"]
        Package = request.env["stock.quant.package"]

        picking = Picking.browse(picking_id)

        if not picking:
            raise UserError(_("Picking with id = %s not found") % picking_id)

        if only_done:
            mls = picking.get_move_lines_done()
        else:
            mls = picking.move_line_ids

        products = Product.union(*[Product.get_product(pb) for pb in product_barcodes])
        filters = [lambda ml: ml.product_id in products]

        if package_names:
            packages = Package.union(*[Package.get_package(pn) for pn in package_names])

            filters.append(
                lambda ml: (
                    ml.result_package_id in packages or ml.u_result_parent_package_id in packages
                )
            )

        if lot_names:
            filters.append(lambda ml: (ml.lot_name in lot_names or ml.lot_id.name in lot_names))

        matched_mls = mls.filtered(lambda ml: all(x(ml) for x in filters))

        if not matched_mls:
            fields = [
                ("picking_id", picking_id),
                ("product_barcode", ",".join(product_barcodes)),
                ("package_name", ",".join(package_names) if package_names else None),
                ("lot_name", ",".join(lot_names) if lot_names else None),
            ]
            citeria = ["%s in [%s]" % (n, v) for n, v in fields if v is not None]
            raise UserError(_("No move line found matching citeria: %s") % ", ".join(citeria))
        return matched_mls.get_info()
