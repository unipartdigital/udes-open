# -*- coding: utf-8 -*-

from odoo import api, models, fields

class StockMove(models.Model):
    _inherit = "stock.move"


    @api.multi
    def _prepare_info(self):
        """ TODO: add docstring

            location_dest_id    {id: stock.location.id, name: stock.location.name, stock.location.barcode}  Cut down location summary, for the destination location
            location_id     As above    Source location
            ordered_qty     float   Ordered quantity
            product_id  {product.product}   Product summary
            product_qty     float   Real quantity expected
            quantity_done   float   Quantity received so far
            move_line_ids   [{stock.move.line}]     The lines associated with this move.
        """
        self.ensure_one()

        return {"id": self.id,
                "location_id": self.location_id.get_info()[0],
                "location_dest_id": self.location_dest_id.get_info()[0],
                "ordered_qty": self.ordered_qty,
                "product_qty": self.product_qty,
                "quantity_done": self.quantity_done,
                "product_id": self.product_id.get_info()[0],
                "moves_line_ids": self.move_line_ids.get_info(),
               }

    @api.multi
    def get_info(self):
        """ TODO: add docstring
        """
        res = []
        for move in self:
            res.append(move._prepare_info())

        return res
