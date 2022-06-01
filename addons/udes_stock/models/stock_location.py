import os.path
from odoo import fields, models, api
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
        "location_id.u_location_storage_format"
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
        string="Location size",
        help="""The size of the location in square feet.""",
        digits=(16, 2),
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
                """
    )

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
