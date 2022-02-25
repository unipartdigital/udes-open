import os.path
from odoo import fields, models


class StockLocation(models.Model):
    _name = "stock.location"
    # Add messages and abstract model to locations
    _inherit = ["stock.location", "mail.thread", "mixin.stock.model"]

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)
    # Add tracking for archiving.
    active = fields.Boolean(tracking=True)

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
