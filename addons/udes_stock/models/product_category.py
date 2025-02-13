from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = "product.category"

    active = fields.Boolean(
        default=True, string="Active", help="Display in list views or searches."
    )
    u_suggest_locations = fields.Boolean(
        string="Enable Suggest Locations",
        default=False,
        help="""
            Computed suggest locations boolean value which depends on value of u_category_suggest_locations.
            
            If u_category_suggest_locations is set then the computed value will be True, otherwise the 
            value will use the Suggest Locations (u_category_suggest_locations) of the nearest ancestor 
            that u_category_suggest_locations is set. If not set in any ancestors, the value will 
            be False. 
            
            This value is used for visibility of the "Suggested Locations" tab in the Desktop.
        """,
        compute="_compute_suggest_locations",
        store=True,
    )
    u_category_suggest_locations = fields.Boolean(
        string="Enable Category Suggest Locations",
        default=False,
        help="""
            The value of this field is used when computing u_suggest_locations value which is a 
            condition for visibility of the tab in the Desktop.
            
            Done in this way in order to set only at the highest level and automatically propagates
            to all children, Also there is the flexibility that any children can have a different
            value if this field is set/unset in any of them.
        """,
    )
    u_suggest_location_ids = fields.Many2many(
        "stock.location",
        "suggested_locations_rel",
        compute="_compute_suggest_location_ids",
        store=True,
        column1="category_id",
        column2="location_id",
        string="Suggest Locations",
        help="""
            Computed suggest locations which depends on value of u_category_suggest_location_ids.
    
            If u_category_suggest_location_ids is set then the computed value will be the same as 
            u_category_suggest_location_ids otherwise the value will use the Suggest Locations 
            (u_category_suggest_location_ids) of the nearest ancestor that 
            u_category_suggest_location_ids has values. If not set on any ancestors, the 
            value will be False. 
        """,
    )
    u_category_suggest_location_ids = fields.Many2many(
        "stock.location",
        "product_category_suggested_locations_rel",
        column1="category_id",
        column2="location_id",
        string="Category Suggest Locations",
        help="""
            The value of this field is used when computing u_suggest_location_ids value which are 
            the locations that will be used when suggesting locations for picking types 
            ByProductCategory and ByProductCategoryOrderpoint.

            Done in this way in order to set only at the highest level and automatically propagates
            to all children, Also there is the flexibility that any children can have a different
            value if this field has or not value in any of them.
        """,
    )

    @api.depends(
        "u_category_suggest_locations",
        "parent_id",
        "parent_id.u_suggest_locations",
        "parent_id.u_category_suggest_locations",
    )
    def _compute_suggest_locations(self):
        """Determine the config about suggest locations.

        If not set on self, get the configuration of the nearest ancestor that is set, return
        False if is not set in any ancestor.
        """
        ProductCategory = self.env["product.category"]

        for category in self:
            suggest_locations = category.u_category_suggest_locations
            if suggest_locations:
                category.u_suggest_locations = suggest_locations
                continue
            # Check ancestors
            parent_suggest_locations = False
            parent = category.parent_id
            while not parent_suggest_locations and parent:
                # No need to read all fields but only parent and storage_format fields
                result = parent.read(fields=["parent_id", "u_category_suggest_locations"])
                if result[0].get("parent_id"):
                    parent_id = result[0].get("parent_id")[0]
                    parent = ProductCategory.browse(parent_id)
                else:
                    parent = False
                parent_suggest_locations = result[0].get("u_category_suggest_locations", False)
            category.u_suggest_locations = parent_suggest_locations

    @api.depends(
        "u_category_suggest_location_ids",
        "parent_id",
        "parent_id.u_suggest_location_ids",
        "parent_id.u_category_suggest_location_ids",
    )
    def _compute_suggest_location_ids(self):
        """Compute suggested locations for product category

        If not set on self, get the suggested locations of the nearest ancestor that is set, return
        False if is not set in any ancestor.
        """
        ProductCategory = self.env["product.category"]

        for category in self:
            suggest_location_ids = category.u_category_suggest_location_ids
            if suggest_location_ids:
                category.u_suggest_location_ids = suggest_location_ids
                continue
            # Check ancestors
            parent_suggest_location_ids = False
            parent = category.parent_id
            while not parent_suggest_location_ids and parent:
                # No need to read all fields but only parent and storage_format fields
                result = parent.read(fields=["parent_id", "u_category_suggest_location_ids"])
                if result[0].get("parent_id"):
                    parent_id = result[0].get("parent_id")[0]
                    parent = ProductCategory.browse(parent_id)
                else:
                    parent = False
                parent_suggest_location_ids = result[0].get("u_category_suggest_location_ids", False)
            if parent_suggest_location_ids:
                category.u_suggest_location_ids = parent_suggest_location_ids
            else:
                category.u_suggest_location_ids = False
