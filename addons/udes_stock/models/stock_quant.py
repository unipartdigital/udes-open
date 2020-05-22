# -*- coding: utf-8 -*-
from odoo import models, _, api
from collections import defaultdict


class StockQuant(models.Model):
    _inherit = "stock.quant"
    _description = "Quant"

    def _gather(self, product_id, location_id, **kwargs):
        """ Call default _gather function, if quant_ids context variable
            is set the resulting quants are filtered by id.
            This allows to reserve specific quants instead of following the default
            policy.
            Context variable quant_ids might contain quants of different products.
        """
        quants = super(StockQuant, self)._gather(product_id, location_id, **kwargs)
        quant_ids = self.env.context.get("quant_ids")
        if quant_ids:
            quants = quants.filtered(lambda q: q.id in quant_ids)
        return quants

    def get_quantity(self):
        """ Returns the total quantity of the quants in self """
        return sum(self.mapped("quantity"))

    def get_quantities_by_key(self, get_key=lambda q: q.product_id, only_available=False):
        """ Returns a dictionary with the total quantity per product, mapped by product_id.
            :kwargs:
                - only_available: Boolean
                    Whether to include those reserved or not in the grouping
                - get_key: a callable which takes a quant and returns the key
            :returns:
                a dictionary with the total quantity per product,
                    mapped by get_key or product_id as default
        """
        products = defaultdict(int)
        for quant in self:
            value = quant.quantity
            if only_available:
                value -= quant.reserved_quantity
            products[get_key(quant)] += value
        return products

    def create_picking(self, picking_type, **kwargs):
        """ Create a picking from quants
            Uses stock.picking create_picking functionality
            :args:
                - picking_type
            :kwargs:
                - Extra args for the create picking
            :returns:
                - picking
        """
        Picking = self.env["stock.picking"]
        product_quantities = self.get_quantities_by_key()
        products_info = [{"product": key, "qty": val} for key, val in product_quantities.items()]
        return Picking.create_picking(picking_type, products_info, **kwargs)
