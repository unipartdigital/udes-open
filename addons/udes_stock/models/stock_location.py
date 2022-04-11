import os.path
from odoo import fields, models


class StockLocation(models.Model):
    _name = "stock.location"
    # Add messages and abstract model to locations
    _inherit = ["stock.location", "mail.thread", "mixin.stock.model"]

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
