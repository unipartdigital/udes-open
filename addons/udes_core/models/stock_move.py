# -*- coding: utf-8 -*-

from odoo import models

class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_info(self):
        """
            Prepares the following info of the move in self:
            - id: int
            - location_dest_id:  {stock.location}
            - location_id: {stock.location}
            - ordered_qty: float
            - product_id: {product.product}
            - product_qty: float
            - quantity_done: float
            - move_line_ids: [{stock.move.line}]
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

    def get_info(self):
        """ Return a list with the information of each move in self.
        """
        res = []
        for move in self:
            res.append(move._prepare_info())

        return res

    def _make_mls_comparison_lambda(self, move_line):
        """ This makes the lambda for
            checking the a move_line
            against move_orign_ids
        """
        lot_name = move_line.lot_id.name or move_line.lot_name
        package = move_line.package_id
        #lot and package
        if lot_name and package:
            return lambda ml: (ml.lot_name == lot_name or \
                               ml.lot_id.name == lot_name) and \
                               ml.result_package_id == package
        # serial
        elif lot_name:
            return lambda ml: ml.lot_name == lot_name or \
                              ml.lot_id.name == lot_name
        # package
        elif package:
            return lambda ml: ml.result_package_id == package
        # products
        else:
            # This probaly isn't to be trusted
            return lambda ml: ml.location_dest_id == move_line.location_id and \
                              ml.product_id == move_line.product_id

    def update_orig_ids(self, origin_ids):
        """ Updates move_orig_ids based on a given set of
            origin_ids for moves in self by finding the ones
            relevent to the current moves.
        """
        origin_mls = origin_ids.mapped('move_line_ids')
        for move in self:
            # Retain incomplete moves
            updated_origin_ids = move.mapped('move_orig_ids').filtered(
                                            lambda x: x.state not in ('done', 'cancel')
                                            )
            for move_line in move.move_line_ids:
                previous_mls = origin_mls.filtered(
                                            self._make_mls_comparison_lambda(move_line)
                                            )
                updated_origin_ids |= previous_mls.mapped('move_id')
            move.move_orig_ids = updated_origin_ids
