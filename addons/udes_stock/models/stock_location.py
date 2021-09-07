# -*- coding: utf-8 -*-

from collections import namedtuple, defaultdict
from datetime import datetime

from odoo import fields, models, _, api
from odoo.exceptions import ValidationError


PI_COUNT_MOVES = "pi_count_moves"
INVENTORY_ADJUSTMENTS = "inventory_adjustments"
PRECEDING_INVENTORY_ADJUSTMENTS = "preceding_inventory_adjustments"

NO_PACKAGE_TOKEN = "NO_PACKAGE"
NEW_PACKAGE_TOKEN = "NEWPACKAGE"

VALID_SERIAL_TRACKING_QUANTITIES = [1, 0]


#
## Auxiliary types
#

StockInfoPI = namedtuple(
    "StockInfoPI",
    [
        "product_id",
        "package_id",
        "original_parent_package_id",
        "result_parent_package_id",
        "lot_id",
    ],
)


class PIOutcome:
    def __init__(self):
        self.moves_inventory = None
        self.adjustment_inventory = None

    def got_inventory_changes(self):
        return self.moves_inventory is not None or self.adjustment_inventory is not None


#
## StockLocation
#


class StockLocation(models.Model):
    _name = "stock.location"
    # Add messages to locations.
    _inherit = ["stock.location", "mail.thread"]

    def _domain_height_category(self):
        """Domain for height product category"""
        Product = self.env["product.template"]
        return Product._domain_height_category()

    def _domain_speed_category(self):
        """Domain for speed product category"""
        Product = self.env["product.template"]
        return Product._domain_speed_category()

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility="onchange")

    u_date_last_checked = fields.Datetime(
        "Date Last Checked", help="The date that the location stock was last checked"
    )

    u_date_last_checked_correct = fields.Datetime(
        "Date Last Checked correct",
        help="The date that the location stock was last checked and all " "products were correct",
    )

    u_quant_policy = fields.Selection(
        string="Location Policy",
        selection=[
            ("all", "Allow all"),
            ("single_product_id", "One product per location"),
            ("single_lot_id_single_product_id_per_package", "One lot/product per package"),
            ("single_package_per_location", "One package per location"),
        ],
    )

    u_height_category_id = fields.Many2one(
        comodel_name="product.category",
        domain=_domain_height_category,
        index=True,
        string="Product Category Height",
        help="Product category height to match with location height.",
    )
    u_speed_category_id = fields.Many2one(
        comodel_name="product.category",
        domain=_domain_speed_category,
        index=True,
        string="Product Category Speed",
        help="Product category speed to match with location speed.",
    )

    u_location_category_id = fields.Many2one(
        comodel_name="stock.location.category",
        index=True,
        string="Location Category",
        help="Used to know which pickers have the right " "equipment to pick from it.",
    )

    u_limit_orderpoints = fields.Boolean(
        index=True,
        string="Limit Orderpoints",
        help="If set, allow only one orderpoint on this location " "and its descendants.",
    )

    u_is_picking_zone = fields.Boolean(
        string="Is A Picking Zone",
        help="Picking Zones are the level to which warehouse-wide Picks are broken down.",
    )

    u_location_is_countable = fields.Selection(
        selection=[
            ("yes", "Yes"),
            ("no", "No"),
        ],
        string="Location Is Countable",
        help="""
    Specifies whether the location is countable. If blank, the value of the parent
    location is used, if applicable.
    """,
    )

    u_is_countable = fields.Boolean(
        compute="_compute_countable_locations",
        store=True,
        string="Is Countable",
        help="""
    Computed countable setting to use for this location.

    The 'Location Is Countable' value set directly on the location will be used if applicable.
    Otherwise the computed value set on the parent location will be used, if applicable.
    """,
    )

    u_state = fields.Selection(
        selection=[
            ("empty", "Empty"),
            ("blocked", "Blocked"),
            ("has_stock", "Has Stock"),
        ],
        compute="_compute_state",
        store=True,
        string="State",
        help="""
    Computed field describing the state of the stock location.
    """,
    )

    @api.multi
    @api.depends("quant_ids", "u_blocked")
    def _compute_state(self):
        """
        Determine the state of the stock location - blocked, empty or has_stock.

        The computed value is only set properly once a location has been created or saved.
        This is because for on the fly changes the location in self will only have access
        to fields in the location form, which doesn't include quant_ids. This can lead to the
        computed value temporarily displaying empty before being set to has_stock once the record
        is saved.
        """
        for location in self:
            state = False

            if location.id and location.usage == "internal":
                if location.u_blocked:
                    state = "blocked"
                elif not location.quant_ids:
                    state = "empty"
                else:
                    state = "has_stock"

            location.u_state = state

    @api.multi
    @api.depends("u_location_is_countable", "location_id", "location_id.u_is_countable")
    def _compute_countable_locations(self):
        """Determine whether stock locations are countable"""
        for location in self:
            is_countable = False
            if location.u_location_is_countable in ["yes", "no"]:
                is_countable = location.u_location_is_countable == "yes"
            else:
                parent = location.location_id
                if parent.u_is_countable:
                    is_countable = True
            location.u_is_countable = is_countable

    def _prepare_info(self, extended=False, load_quants=False):
        """
        Prepares the following info of the location in self:
        - id: int
        - name: string
        - barcode: string

        When load_quants is True also return:
        - quant_ids: [{stock.quants}]

        When extended is True also return:
        - u_blocked: bool
        - u_blocked_reason: string
        """
        self.ensure_one()

        info = {
            "id": self.id,
            "name": self.name,
            "barcode": self.barcode,
        }

        if load_quants:
            info["quant_ids"] = self.quant_ids.get_info()

        if extended:
            info["u_blocked"] = self.u_blocked
            info["u_blocked_reason"] = self.u_blocked_reason
            if self.u_location_category_id:
                info["u_location_category_id"] = self.u_location_category_id.get_info()[0]

        return info

    def get_info(self, **kwargs):
        """Return a list with the information of each location in self."""
        res = []
        for loc in self:
            res.append(loc._prepare_info(**kwargs))

        return res

    def get_location(self, location_identifier):
        """Get locations from a name, barcode, or id."""
        if isinstance(location_identifier, int):
            domain = [("id", "=", location_identifier)]
        elif isinstance(location_identifier, str):
            domain = [
                "|",
                ("barcode", "=", location_identifier),
                ("name", "=", location_identifier),
            ]
        else:
            raise ValidationError(
                _("Unable to create domain for location search from " "identifier of type %s")
                % type(location_identifier)
            )

        results = self.search(domain)

        if not results:
            raise ValidationError(
                _("Location not found for identifier %s") % str(location_identifier)
            )

        if len(results) > 1:
            raise ValidationError(
                _("Too many locations found for identifier %s") % str(location_identifier)
            )

        return results

    #
    ## Perpetual Inventory
    #

    def _check_obj_locations(self, loc_keys, obj):
        Location = self.env["stock.location"]

        for key in loc_keys:
            loc_id = int(obj[key])

            if not Location.browse(loc_id).exists():
                raise ValidationError(
                    _("The request has an unknown location, " "id: '%d'.") % loc_id
                )

    def _validate_inventory_adjustment_request(self, request):
        """
        Ensures that the specified product exists and that
        its `tracking` value is compatible with the request
        lot (which may or may not be specified).

        Raises a ValidationError otherwise.
        """
        Product = self.env["product.product"]

        product = Product.get_product(int(request["product_id"]))

        # Ignore conflicts of tracked vs untracked if we are removing existing
        # stock
        if request["quantity"] == 0:
            return

        if "lot_name" not in request:
            if product.tracking != "none":
                raise ValidationError(
                    _("Product '%s' is tracked, but the lot name is not " "specified.")
                    % product.name
                )
        else:
            if product.tracking == "lot":
                return
            elif product.tracking == "serial":
                qty = int(request["quantity"])

                if qty not in VALID_SERIAL_TRACKING_QUANTITIES:
                    raise ValidationError(
                        _("Product '%s' is tracked, but the quantity is %d.") % (product.name, qty)
                    )
            else:
                raise ValidationError(
                    _("Product '%s' is not tracked, but a lot name has been " "specified.")
                    % product.name
                )

    def _validate_perpetual_inventory_request(self, request):
        keys = ["location_id", "location_dest_id"]

        if PI_COUNT_MOVES in request:
            for obj in request[PI_COUNT_MOVES]:
                self._check_obj_locations(keys, obj)

        if PRECEDING_INVENTORY_ADJUSTMENTS in request:
            if not request.get(INVENTORY_ADJUSTMENTS):
                raise ValidationError(
                    _(
                        "You must specify inventory adjustments if you require "
                        "preceding adjustments."
                    )
                )

            for pre_adjs_req in request[PRECEDING_INVENTORY_ADJUSTMENTS]:
                self._check_obj_locations(keys[:1], pre_adjs_req)

                for req in pre_adjs_req[INVENTORY_ADJUSTMENTS]:
                    self._validate_inventory_adjustment_request(req)

        if INVENTORY_ADJUSTMENTS in request:
            for req in request[INVENTORY_ADJUSTMENTS]:
                self._validate_inventory_adjustment_request(req)

    def process_perpetual_inventory_request(self, request):
        """
        Executes the specified PI request by processing PI count
        moves, inventory adjustments, and preceding inventory
        adjustments. Updates the PI date time attributes (last
        check dates) accordingly.

        Expects a singleton.
        Expects a `request` argument that complies with the PI
        endpoint request schema.

        Raises a ValidationError in case of invalid request (e.g.
        one of the specified locations, packages, or products
        doesn't exist).

        Returns True.
        """
        self.ensure_one()
        self._validate_perpetual_inventory_request(request)
        pi_outcome = PIOutcome()

        if PI_COUNT_MOVES in request:
            pi_outcome.moves_inventory = self._process_pi_count_moves(request[PI_COUNT_MOVES])

        if INVENTORY_ADJUSTMENTS in request:
            pi_outcome.adjustment_inventory = self._process_inventory_adjustments(
                request[INVENTORY_ADJUSTMENTS]
            )
            for pre_adjs_req in request.get(PRECEDING_INVENTORY_ADJUSTMENTS, []):
                self._process_single_preceding_adjustments_request(
                    pre_adjs_req, pi_outcome.adjustment_inventory
                )

        self._process_pi_datetime(pi_outcome)

        return True

    def _process_pi_datetime(self, pi_outcome):
        current_time = datetime.now()
        self.write({"u_date_last_checked": current_time})

        if not pi_outcome.got_inventory_changes():
            # No PI changes - the location is in a correct state
            self.write({"u_date_last_checked_correct": current_time})

    # PI Count Moves

    def _process_pi_count_moves(self, count_moves, picking_type_id=None):
        """
        Returns the modified inventory in case consistent move
        changes are specified in the request, None otherwise.

        Creates an internal transfer by default, if no
        picking type is specified.

        Raises a ValidationError in case of invalid request.
        """
        Picking = self.env["stock.picking"]
        Users = self.env["res.users"]

        if picking_type_id is None:
            warehouse = Users.get_user_warehouse()
            picking_type_id = warehouse.u_pi_count_move_picking_type.id

        created_pickings = Picking.browse()

        for count_move in count_moves:
            created_pickings += self._create_pi_count_move_picking(count_move, picking_type_id)

        return created_pickings if created_pickings else None

    def _create_pi_count_move_picking(self, count_move, picking_type_id):
        """
        Validates the single PI count move request.
        Creates and returns the related picking.

        Raises a ValidationError in case of invalid request
        or if the quants (either specified in the request or
        related to a package) are already reserved.
        """
        Package = self.env["stock.quant.package"]
        Picking = self.env["stock.picking"]
        Quant = self.env["stock.quant"]

        # NB: locations are already validated
        location_id = int(count_move["location_id"])
        location_dest_id = int(count_move["location_dest_id"])
        quants = None
        quant_ids = []
        package = False
        result_parent_package = False
        if "package_id" in count_move:
            package = Package.browse(int(count_move["package_id"])).exists()
        if package:
            # NB: ignoring a possible 'quant_ids' entry, in case
            # there's no previous schema validation
            quants = package._get_contained_quants()
            quant_ids = quants.ids
            if "parent_package_barcode" in count_move:
                parent_package_name = count_move["parent_package_barcode"]
                if (
                    NO_PACKAGE_TOKEN in parent_package_name
                    or NEW_PACKAGE_TOKEN in parent_package_name
                ):
                    raise ValidationError(_("Unnexpected parent package name: forbidden token"))
                result_parent_package = Package.get_package(parent_package_name, create=True)
        elif "quant_ids" in count_move:
            quant_ids = [int(x) for x in count_move["quant_ids"]]
            quants = Quant.browse(quant_ids)
            num_found_quants = len(quants.exists())

            if num_found_quants != len(quant_ids):
                raise ValidationError(
                    _("Unknown quants in PI count move request; searched for " "%d, found %d.")
                    % (len(quant_ids), num_found_quants)
                )
        else:
            raise ValidationError(
                _(
                    "Invalid request; missing one of quant_ids or "
                    "package_id entries in PI count move request."
                )
            )

        if any(map(lambda q: q.reserved_quantity > 0, quants)):
            raise ValidationError(_("Some quants are already reserved."))

        picking = Picking.create_picking(
            quant_ids,
            location_id,
            picking_type_id=picking_type_id,
            location_dest_id=location_dest_id,
        )
        if result_parent_package:
            picking.move_line_ids.write({"u_result_parent_package_id": result_parent_package.id})
        picking.move_line_ids.mark_as_done()

        picking_details = Picking.get_stock_investigation_message(quants)

        if picking_details:
            picking_header = "PI Count Move created with: <br>"
            picking.message_post(body=_(picking_header + picking_details))

        return picking

    # PI Inventory Adjustments

    def _process_single_preceding_adjustments_request(self, pre_adjs_request, next_adjusted_inv):
        """
        Process the inventory adjustments for the location
        specified in the request.
        Assigns the next inventory field of the new inventory
        to the specified next adjusted inventory instance.

        Raises a ValidationError in case the location does not
        exist.
        """
        Location = self.env["stock.location"]

        location = Location.get_location(int(pre_adjs_request["location_id"]))
        inv = location._process_inventory_adjustments(pre_adjs_request[INVENTORY_ADJUSTMENTS])
        inv.u_next_inventory_id = next_adjusted_inv

    def _process_inventory_adjustments(self, adjustments_request):
        """
        Returns the modified inventory in case consistent
        adjustments changes are specified in the request,
        None otherwise.

        Raises a ValidationError in case of invalid request.
        """
        Inventory = self.env["stock.inventory"]
        InventoryLine = self.env["stock.inventory.line"]

        stock_drift = self._get_stock_drift(adjustments_request)

        if not stock_drift:
            return

        inventory_adjustment = Inventory.create(
            {
                "name": "PI inventory adjustment " + self.name,
                "location_id": self.id,
                "filter": "none",
                "state": "confirm",
            }
        )

        for stock_info, quantity in stock_drift.items():
            InventoryLine.create(
                {
                    "inventory_id": inventory_adjustment.id,
                    "product_id": stock_info.product_id,
                    "product_qty": quantity,
                    "location_id": self.id,
                    "package_id": stock_info.package_id,
                    "u_package_parent_package_id": stock_info.original_parent_package_id,
                    "u_result_parent_package_id": stock_info.result_parent_package_id,
                    "prod_lot_id": stock_info.lot_id,
                }
            )

        return inventory_adjustment

    def _get_stock_drift(self, adjustments_request):
        """
        Returns a dictionary where keys are StockInfoPI instances
        and values are integers representing a product quantity.
        Each StockInfo is the result of the processing of an
        adjustments_request entry.

        Creates a lot for a given product if necessary, when the
        related lot name doesn't exist.

        Raises a ValidationError in case any specified product
        or package doesn't exist.
        """
        Product = self.env["product.product"]
        Package = self.env["stock.quant.package"]
        Lot = self.env["stock.production.lot"]
        wh = self.env.user.get_user_warehouse()
        stock_drift = {}
        new_packages = {}

        # Group quantities by product and reserved packages
        no_package_vals = defaultdict(int)
        adj_reqs = []
        for adj in adjustments_request:
            pn = adj["package_name"]
            if adj.get("lot_name"):
                adj_reqs.append(adj)
                continue
            if NO_PACKAGE_TOKEN in pn or pn in wh.reserved_package_name:
                no_package_vals[adj["product_id"]] += adj["quantity"]
            else:
                adj_reqs.append(adj)

        # Replace requests with values passed through by reserved filter
        adjustments_request = adj_reqs

        # Read them to adjustments_request
        new_adjs = []
        for product_id, quantity in no_package_vals.items():
            new_adjs.append(
                {
                    "product_id": product_id,
                    "package_name": NO_PACKAGE_TOKEN,
                    "quantity": quantity,
                }
            )
        adjustments_request.extend(new_adjs)
        # Look through all quants not in packages within location and index
        # the quantities by product, as we have collected quantities by product
        # for the adjustments without package this allows us to directly compare
        # and skip unchanged loose product quantities
        products_and_quantities = {}
        for quant in self.mapped("quant_ids"):
            if not quant.package_id:
                products_and_quantities[quant.product_id] = quant.quantity

        # Go through (potentially modified) adjustments_request
        for adj in adjustments_request:
            product = Product.get_product(int(adj["product_id"]))
            # determine the package
            package_name = adj["package_name"]
            package = None
            if NO_PACKAGE_TOKEN in package_name:
                if products_and_quantities.get(product) == adj["quantity"]:
                    continue
            elif NEW_PACKAGE_TOKEN in package_name:
                if package_name in new_packages:
                    package = new_packages[package_name]
                else:
                    package = Package.create({})
                    new_packages[package_name] = package
            else:
                # It might be a new package, so create=True
                package = Package.get_package(package_name, create=True)

            original_parent_package_id = False
            if package:
                original_parent_package_id = package.package_id.id if package.package_id else False

            package_id = False if package is None else package.id

            parent_package_name = adj.get("parent_package_name")
            parent_package = False
            if parent_package_name and NO_PACKAGE_TOKEN not in parent_package_name:
                parent_package = Package.get_package(parent_package_name, create=True)

            parent_package_id = parent_package.id if parent_package else False

            # determine the lot

            lot_id = False
            if "lot_name" in adj:
                lot = Lot.get_lot(adj["lot_name"], product.id, create=True)
                lot_id = lot.id

            # add the entry

            info = StockInfoPI(
                product.id, package_id, original_parent_package_id, parent_package_id, lot_id
            )
            stock_drift[info] = adj["quantity"]

        return stock_drift

    def get_quant_policy(self):
        self.ensure_one()
        my_policy = self.u_quant_policy
        if not my_policy and self.location_id:
            return self.location_id.get_quant_policy()
        return my_policy

    def apply_quant_policy(self):
        for loc in self:
            policy = loc.get_quant_policy()
            if policy:
                func = getattr(self, "_apply_quant_policy_" + policy, None)
                if func:
                    func(policy, loc)

    def _apply_quant_policy_single_product_id(self, policy, loc):
        if policy == "single_product_id" and len(loc.quant_ids.mapped("product_id")) > 1:
            raise ValidationError(_("Location %s cannot contain more than one product." % loc.name))

    def _apply_quant_policy_single_lot_id_single_product_id_per_package(self, policy, loc):
        if policy == "single_lot_id_single_product_id_per_package":
            loc.quant_ids.mapped("package_id")
            for package, quants in loc.quant_ids.groupby("package_id"):
                if len(quants.mapped("lot_id")) > 1 or len(quants.mapped("product_id")) > 1:
                    raise ValidationError(
                        _("Package %s cannot contain more than one lot or product") % package.name
                    )

    def _apply_quant_policy_single_package_per_location(self, policy, loc):
        if policy == "single_package_per_location" and len(loc.mapped("quant_ids.package_id")) > 1:
            raise ValidationError(_("Location %s should only contain one package.") % loc.name)

    @api.constrains("u_quant_policy", "location_id")
    def apply_location_policy_change_to_descendants(self):
        examine_locations = self.env["stock.location"].search(
            [("location_id", "child_of", self.ids)]
        )

        for examine_location in examine_locations:
            if examine_location.quant_ids:
                examine_location.apply_quant_policy()

    def limits_orderpoints(self):
        """Determines whether this location, or an ancestor, permits only a
        single orderpoint on itself.

        Returns: a boolean: True if limited, False otherwise.
        """
        self.ensure_one()
        limited = self.search([("u_limit_orderpoints", "=", True)])
        return bool(self.search_count([("id", "child_of", limited.ids), ("id", "=", self.id)]))

    def is_compatible_package(self, package_name):
        """The package with name package_name is compatible
        with the location in self if either:
        - it does not exist;
        - it is in the location represented by self.
        """
        Package = self.env["stock.quant.package"]
        self.ensure_one()
        package = Package.get_package(package_name, no_results=True)
        if package and package.location_id:
            return package.location_id == self
        return True

    @api.multi
    def get_picking_zone(self):
        """
        Get the location that is the picking zone for the location in self.
        A picking zone is a location with u_is_picking_zone == True.
        If self is a picking zone, it is returned, otherwise successive parent
        locations are checked, and the first one which is a picking zone
        is returned.
        If no picking zone is found, returns an empty stock.location recordset.
        :return: A stock.location() recordset with 1 or 0 records in.
        """
        self.ensure_one()
        zone = self.browse()
        location = self
        while location and not zone:
            if location.u_is_picking_zone:
                zone = location
            location = location.location_id
        return zone

    def button_view_child_locations(self):
        """Return a tree view of all descendants of the location in self"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("%s - Child Locations") % (self.name),
            "res_model": "stock.location",
            "view_type": "form",
            "view_mode": "tree,form",
            "domain": [("id", "!=", self.id), ("id", "child_of", self.id)],
            "context": {"default_location_id": self.id},
        }


class Orderpoint(models.Model):

    _inherit = "stock.warehouse.orderpoint"

    @api.onchange("location_id")
    @api.constrains("location_id")
    def _is_limited(self):
        """Prevents creating a second order point on a location.

        If the location or an ancestor is configured to only allow a single
        order point.

        Raises a ValidationError if the constraint is breached.
        """
        self.ensure_one()
        Orderpoint = self.env["stock.warehouse.orderpoint"]
        orderpoints = Orderpoint.search(
            [
                ("location_id", "=", self.location_id.id),
            ]
        )
        orderpoints -= self
        if not orderpoints:
            return
        if not self.location_id.limits_orderpoints():
            return
        names = ", ".join(orderpoints.mapped("product_id.name"))
        raise ValidationError(
            _("An order point for location {} already exists on " "{}.").format(
                self.location_id.name, names
            )
        )
