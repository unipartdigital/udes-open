# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _unreserve_initial_demand(self, new_move):
        """ Override stock default function to keep the old move lines,
            so there is no need to create them again
        """
        self.mapped('move_line_ids')\
            .filtered(lambda x: x.qty_done == 0.0)\
            .write({'move_id': new_move, 'product_uom_qty': 0})

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

    def split_out_move_lines(self, move_lines):
        """ Split sufficient quantity from self to cover move_lines, and
        attach move_lines to the new move. Return the move that now holds all
        of move_lines.
        If self is completely covered by move_lines, it will be removed from
        its picking and returned.
        Preconditions: self is a single move,
                       all moves_line are attached to self
        :return: The (possibly new) move that covers all of move_lines,
                 not currently attached to any picking.
        """
        self.ensure_one()
        if not all(ml.move_id == self for ml in move_lines):
            raise ValueError(_("Cannot split move lines from a move they are"
                               "not part of."))

        if move_lines == self.move_line_ids and \
                not self.move_orig_ids.filtered(
                    lambda x: x.state not in ('done', 'cancel')):
            bk_move = self
            bk_move.write({'picking_id': None})
        else:
            # TODO: consider using odoo core stock.move._split?
            total_ordered_qty = sum(move_lines.mapped('ordered_qty'))
            total_initial_qty = sum(move_lines.mapped('product_uom_qty'))
            bk_move = self.copy({
                'picking_id': False,
                'move_line_ids': [],
                'move_orig_ids': [],
                'ordered_qty': total_ordered_qty,
                'product_uom_qty': total_initial_qty,
                'state': 'assigned',
            })
            move_lines.write({
                'move_id': bk_move.id,
                'state': 'assigned',
                'picking_id': None,
            })
            self.with_context(bypass_reservation_update=True).write({
                'ordered_qty': self.ordered_qty - total_ordered_qty,
                'product_uom_qty': self.product_uom_qty - total_initial_qty,
            })

            if self.move_orig_ids:
                (bk_move | self).update_orig_ids(self.move_orig_ids)

        return bk_move

    def _action_assign(self):
        res = super(StockMove, self)._action_assign()
        for picking_type in self.mapped('picking_type_id'):
            self.filtered(lambda m: m.picking_type_id == picking_type). \
                post_reservation_split()

    def post_reservation_split(self):
        """
        group the move lines by the splitting criteria
        for each resulting group of stock.move.lines:
            create a new picking
            split any stock.move records that are only partially covered by the
                group of stock.move.lines
            attach the stock.moves and stock.move.lines to the new picking.
        """
        Picking = self.env['stock.picking']

        picking_type = self.mapped('picking_type_id')
        picking_type.ensure_one()

        if not picking_type.u_move_line_key_format:
            return

        pickings = self.mapped('picking_id')
        mls_by_key = self.mapped('move_line_ids').group_by_key()

        for key, ml_group in mls_by_key.items():
            touched_moves = ml_group.mapped('move_id')

            if len(touched_moves.mapped('location_id')) > 1 or \
                    len(touched_moves.mapped('location_dest_id')) > 1:
                raise UserError(_('Please contact an Administrator.\n'
                                  'Move Line grouping has generated a group of'
                                  'moves that has more than one source or '
                                  'destination location. Aborting. key: "%s", '
                                  'location_ids: "%s", location_dest_ids: "%s"'
                                  '') % (key, touched_moves.mapped('location_id'),
                                         touched_moves.mapped('location_dest_id')))

            group_moves = self.env['stock.move']
            for move in touched_moves:
                move_mls = ml_group.filtered(lambda l: l.move_id == move)

                if move_mls != move.move_line_ids:
                    # The move is not entirely contained by the move lines
                    # for this grouping. Need to split the move.
                    group_moves |= move.split_out_move_lines(move_mls)
                else:
                    group_moves |= move

            Picking._new_picking_for_group(key, group_moves)

        empty_picks = pickings.filtered(lambda p: len(p.move_lines) == 0)
        if empty_picks:
            _logger.info(_("Cancelling empty picks after splitting."))
            # action_cancel does not cancel a picking with no moves.
            empty_picks.write({
                'state': 'cancel',
                'is_locked': True
            })
