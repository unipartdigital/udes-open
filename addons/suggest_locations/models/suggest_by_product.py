# -*- coding: utf-8 -*-
from odoo import models, fields, _
from itertools import groupby
from .suggest_locations_policy import SuggestLocationPolicy, get_selection


class ByProduct(SuggestLocationPolicy):
    """Find locations based on other placed that product is stored"""

    preprocessing = False

    @classmethod
    def name(cls):
        return "by_product"

    def get_values_from_mls(self, mls):
        return {
            "product": mls.product_id.ensure_one(),
            "location": mls.picking_id.location_dest_id.ensure_one(),
        }

    def _get_product_from_dict(self, values):
        """Get the product from the values, assumed ot be the int id of a product"""
        Product = self.env["product.product"]
        product_id = values.get("product_id")
        if not product_id:
            raise ValueError(_("No product found"))
        return Product.browse(product_id)

    def _get_picking_from_dict(self, values):
        """Get the picking from the values, assumed ot be the int id of a product"""
        Picking = self.env["stock.picking"]
        picking_id = values.get("picking_id")
        if not picking_id:
            raise ValueError(_("No picking found"))
        return Picking.browse(picking_id)

    def get_values_from_dict(self, values):
        picking = self._get_picking_from_dict(values)
        return {
            "product": self._get_product_from_dict(values),
            "location": picking.location_dest_id,
        }

    def get_locations(self, product, location, **kwargs):
        """Get all locations that are the location or child of its location with the same
        product
        """
        Quant = self.env["stock.quant"]
        # Add order="id" for performance as we don't care about the order
        product_quants = Quant.search(
            [("location_id", "child_of", location.id), ("product_id", "=", product.id),],
            order="id",
        )
        return product_quants.location_id

    def iter_mls(self, mls):
        for _prod, grouped_mls in mls.groupby("product_id"):
            yield grouped_mls


class PickingType(models.Model):

    _inherit = "stock.picking.type"

    u_suggest_locations_policy = fields.Selection(selection_add=[get_selection(ByProduct)])
