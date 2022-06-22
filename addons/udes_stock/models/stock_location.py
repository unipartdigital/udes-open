import os.path
from odoo import fields, models, api, _
from .stock_picking_type import TARGET_STORAGE_FORMAT_OPTIONS


class StockLocation(models.Model):
    _name = "stock.location"
    # Add messages and abstract model to locations
    _inherit = ["stock.location", "mail.thread", "mixin.stock.model"]
    MSM_STR_DOMAIN = ("name", "barcode")

    @api.depends(
        "u_location_storage_format",
        "location_id",
        "location_id.u_storage_format",
        "location_id.u_location_storage_format",
    )
    def _compute_storage_format(self):
        """Determine the storage format of the location.

        If not set on self, get the format of the nearest ancestor that specifies a format.
        """
        Location = self.env["stock.location"]

        for location in self:
            storage_format = location.u_location_storage_format
            if storage_format:
                location.u_storage_format = storage_format
                continue
            # Check ancestors
            parent_storage_format = False
            parent = location.location_id
            while not parent_storage_format and parent:
                # No need to read all fields but only parent and storage_format fields
                result = parent.read(fields=["location_id", "u_location_storage_format"])
                if result[0].get("location_id"):
                    parent_id = result[0].get("location_id")[0]
                    parent = Location.browse(parent_id)
                else:
                    parent = False
                parent_storage_format = result[0].get("u_location_storage_format", False)
            location.u_storage_format = parent_storage_format

    def _domain_speed_category(self):
        """Domain for speed product category"""
        Product = self.env["product.template"]
        return Product._domain_speed_category()

    def _domain_height_category(self):
        """Domain for speed product category"""
        Product = self.env["product.template"]
        return Product._domain_height_category()

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)
    # Add tracking for archiving.
    active = fields.Boolean(tracking=True)
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
    u_size = fields.Float(
        string="Location size", help="The size of the location in square feet.", digits=(16, 2)
    )
    u_location_category_id = fields.Many2one(
        comodel_name="stock.location.category",
        index=True,
        string="Location Category",
        help="Used to know which pickers have the right equipment to pick from it.",
    )

    u_limit_orderpoints = fields.Boolean(
        index=True,
        string="Limit Orderpoints",
        help="If set, allow only one orderpoint on this location and its descendants.",
    )
    u_storage_format = fields.Selection(
        TARGET_STORAGE_FORMAT_OPTIONS,
        string="Storage Format",
        compute="_compute_storage_format",
        help="""
                Computed storage format to use for the location.

                The format set directly on the location will be used if applicable.
                Otherwise the format of the nearest ancestor with a format specified will be used.
                """,
        store=True,
    )
    u_location_storage_format = fields.Selection(
        TARGET_STORAGE_FORMAT_OPTIONS,
        string="Location Storage Format",
        help="""
                Storage format specified directly for this location.

                If not set then the location will use the format
                of the nearest ancestor that has a format specified.
                """,
    )
    u_location_is_countable = fields.Selection(
        selection=[("yes", "Yes"), ("no", "No")],
        string="Location Is Countable",
        help="""
    Specifies whether the location is countable. If blank, the value of the parent
    location is used, if applicable.
    """,
    )
    u_is_countable = fields.Boolean(
        compute="_compute_is_countable",
        store=True,
        string="Is Countable",
        help="""
    Computed countable setting to use for this location.
    The 'Location Is Countable' value set directly on the location will be used if applicable.
    Otherwise the computed value set on the parent location will be used, if applicable.
    """,
    )
    u_countable_state = fields.Selection(
        selection=[("empty", "Empty"), ("has_stock", "Has Stock"), ("archived", "Archived")],
        compute="_compute_countable_state",
        store=True,
        string="State",
        help="""
        Computed field describing the state of a stockable location that is countable,
        see u_countable field.""",
    )

    @api.depends("u_location_is_countable", "location_id", "location_id.u_is_countable")
    def _compute_is_countable(self):
        """Determine whether stock locations are countable"""
        for location in self:
            is_countable = False
            if location.u_location_is_countable in ("yes", "no"):
                is_countable = location.u_location_is_countable == "yes"
            else:
                parent = location.location_id
                if parent.u_is_countable:
                    is_countable = True
            location.u_is_countable = is_countable

    @api.depends("quant_ids", "usage", "active", "u_is_countable")
    def _compute_countable_state(self):
        """
        Determine the state of the stock location via _set_countable_state if the location
        is a valid one to be counted.
        The computed value is only set properly once a location has been created or saved.
        This is because for on the fly changes the location in self will only have access
        to fields in the location form, which doesn't include quant_ids. This can lead to the
        computed value temporarily displaying empty before being set to has_stock once the record
        is saved.
        """

        for location in self:
            state = False

            if location.id and location.usage == "internal" and location.u_is_countable:
                state = location._set_countable_state()

            location.u_countable_state = state

    def _set_countable_state(self):
        """
        Method to set the countable state of a location called by the _compute state
        method incase it needs to be overridden elsewhere. It assumes the location is indeed countable.
        Returns a string value
        """
        Quant = self.env["stock.quant"]
        self.ensure_one()
        if not self.active:
            return "archived"
        elif not Quant.search_count([("location_id", "=", self.id)]):
            return "empty"
        else:
            return "has_stock"

    def get_common_ancestor(self):
        """
        Returns the smallest location containing all the locations in self.
        Locations are considered to contain themselves.

        :returns:
            The stock.location containing all the locations in self,
            or an empty stock.location recordset if there is no such location.
        """
        Location = self.env["stock.location"]

        if len(self) <= 1:
            return self

        # Each location's parent_path is a "/"-delimited string of parent ids
        # including itself
        common_path = os.path.commonpath(self.mapped("parent_path"))
        id = common_path.split("/")[-1]
        if id == "":
            return Location.browse()
        else:
            return Location.browse(int(id))

    def limits_orderpoints(self):
        """Determines whether this location, or an ancestor, permits only a
        single orderpoint on itself.

        Returns: a boolean: True if limited, False otherwise.
        """
        self.ensure_one()
        limited = self.search([("u_limit_orderpoints", "=", True)])
        return bool(self.search_count([("id", "child_of", limited.ids), ("id", "=", self.id)]))

    def button_view_child_locations(self):
        """Return a tree view of all descendants of the location in self"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("%s - Child Locations") % self.name,
            "res_model": "stock.location",
            "view_type": "form",
            "view_mode": "tree,form",
            "domain": [("id", "!=", self.id), ("id", "child_of", self.id)],
            "context": {"default_location_id": self.id},
        }

    @api.model
    def get_available_stock_locations(self):
        """Method returns stock locations that are considered (along with
         their children) stock available for fulfilling orders. Should be
        overridden where necessary"""
        return self.env.ref("stock.stock_location_stock")
