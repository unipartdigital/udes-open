# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from .main import UdesApi
from odoo.exceptions import ValidationError, UserError


def _get_location(env, lid, lname, lbarcode):
    Location = env["stock.location"]
    identifier = lid or lname or lbarcode
    if not identifier:
        raise ValidationError(_("You need to provide an id, name or barcode for the location."))
    return Location.get_location(identifier)


class Location(UdesApi):
    @http.route("/api/stock-location/", type="json", methods=["GET"], auth="user")
    def get_location(
        self,
        location_id=None,
        location_name=None,
        location_barcode=None,
        load_quants=False,
        check_blocked=False,
    ):
        """ Search for a location by id, name or barcode and returns a
            stock.location object that match the given criteria.

            @param (optional) location_id
                The location's id
            @param (optional) location_name
                This is a string that entirely matches the name
            @param (optional) location_barcode
                This is a string that entirely matches the barcode
            @param (optional) load_quants: Boolean (default = false)
                Load the quants associated with a location.
            @param (optional) check_blocked:  Boolean (default = false)
                When enabled, checks if the location is blocked, in which case
                an error will be raise.
        """
        location = _get_location(request.env, location_id, location_name, location_barcode)

        if check_blocked:
            location.check_blocked()

        # Update scanning start date on location
        location.update_scanning_date_start()

        return location.get_info(extended=True, load_quants=load_quants)[0]

    @http.route("/api/stock-location-pi-count/", type="json", methods=["POST"], auth="user")
    def pi_count(self, pi_request):
        """
            Process a Perpetual Inventory (PI) count request by creating
            inventory adjustments and count moves as specified.

            Returns True in case of success.

            Raises a ValidationError in case of invalid request or if
            any of the specified location is unknown.

            @param pi_request is a JSON object with the "pi_count_moves",
            "inventory_adjustments", "preceding_inventory_adjustments"
            and "location_id" entries
        """
        Location = request.env["stock.location"]

        location_id = None

        try:
            location_id = int(pi_request.get("location_id"))
        except ValueError:
            pass

        if location_id is None:
            raise ValidationError(_("You need to provide a valid id for the location."))

        location = Location.get_location(location_id)

        return location.with_context(is_mobile=True).process_perpetual_inventory_request(pi_request)

    @http.route("/api/stock-location/block/", type="json", methods=["POST"], auth="user")
    def block(self, reason, location_id=None, location_name=None, location_barcode=None):
        """
            Blocks the specified location and creates a Stock
            Investigation for it.

            Raises a ValidationError if the specified location is
            unknown or already blocked.

            Returns True in case of success.

            @param <ident>  location_id of the location to block
            @param reason   Reason for the location being blocked
        """
        Picking = request.env["stock.picking"]
        ResUsers = request.env["res.users"]

        location = _get_location(request.env, location_id, location_name, location_barcode)

        # Raise if location is already blocked, as we can't raise
        # SI in a blocked location
        if location.u_blocked is True:
            raise ValidationError(_("Location is already blocked."))

        # Create a SI in this location
        si_picking_type = ResUsers.get_user_warehouse().u_stock_investigation_picking_type
        Picking.create(
            {
                "location_id": location.id,
                "location_dest_id": si_picking_type.default_location_dest_id.id,
                "picking_type_id": si_picking_type.id,
            }
        )

        # Block the location (after creating SI, otherwise Picking.create fails)
        location.sudo().write({"u_blocked": True, "u_blocked_reason": reason})

        return True

    @http.route(
        "/api/stock-location/is_compatible_package/", type="json", methods=["GET"], auth="user"
    )
    def is_compatible_package_to_location(
        self,
        package_name,
        location_id=None,
        location_name=None,
        location_barcode=None,
        picking_id=None,
    ):
        """
            Checks that the package is in the specified location,
            in case it exists. It also checks if the package is assigned
            to another result_package_id in more than one destination location
            on stock.move.line and raise UserError in that case.
            Refer to the API specs in the README for more details.
        """
        Package = request.env["stock.quant.package"]
        context = dict(request.env.context)
        context.update(picking_id=picking_id)

        location = _get_location(request.env, location_id, location_name, location_barcode)

        if not package_name:
            raise ValidationError(_("You need to provide a package name."))

        res = location.is_compatible_package(package_name)

        package = Package.get_package(package_name, no_results=True)

        # Usecase for picking returns
        if package and picking_id:
            # Set picking_id in context
            sml = package.with_context(context).current_picking_move_line_ids
            pack_location = sml.mapped("location_dest_id")
            if pack_location and (len(pack_location) > 1 or location != pack_location):
                raise UserError(
                    _("You should not put the contents of a package in different locations.")
                )
        return res
