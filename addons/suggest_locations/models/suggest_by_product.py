# -*- coding: utf-8 -*-
from odoo import models, fields, _
from itertools import groupby
from .suggest_locations_policy import SuggestLocationPolicy, get_selection


class ByProduct(SuggestLocationPolicy):
    """Find locations based on other placed that product is stored"""

    @classmethod
    def name(cls):
        return "by_product"

    def get_values_from_mls(self, mls):
        return {
            "product": mls.product_id.ensure_one(),
            "parent_location": mls.u_picking_type_id.default_location_dest_id.ensure_one(),
        }

    def _get_product_from_dict(self, values):
        """ Get the product from the values """
        product_id = values.get("product_id")
        if not product_id:
            raise ValueError(_("No product found"))

        if isinstance(product_id, int):
            return self.env["product.product"].browse(product_id)
        elif isinstance(product_id, models.BaseModel):
            return product_id.ensure_one()

    def _get_picking_from_dict(self, values):
        """ Get the picking from the values 
            Note: Cannot just use the picking because in _prepare_move_lines we 
            call suggest_locations but couldn't add a field picking_rec, already
            has picking_id
        """
        picking_id = values.get("picking_id")
        if not picking_id:
            raise ValueError(_("No picking found"))
        if isinstance(picking_id, int):
            picking = self.env["stock.picking"].browse(picking_id)
        elif isinstance(picking_id, models.BaseModel):
            picking = picking_id
        return picking

    def get_values_from_dict(self, values):
        picking = self._get_picking_from_dict(values)
        return {
            "product": self._get_product_from_dict(values),
            "parent_location": picking.picking_type_id.default_location_dest_id.ensure_one(),
            "picking_id": picking,
        }

    def get_locations(self, product, parent_location, **kwargs):
        Quant = self.env["stock.quant"]
        product_quants = Quant.search(
            [("location_id", "child_of", parent_location.id), ("product_id", "=", product.id),]
        )
        return product_quants.location_id

    def iter_mls(self, mls):
        for _prod, grouped_mls in mls.groupby("product_id"):
            yield grouped_mls


class PickingType(models.Model):

    _inherit = "stock.picking.type"

    u_suggest_locations_policy = fields.Selection(selection_add=[get_selection(ByProduct)])
