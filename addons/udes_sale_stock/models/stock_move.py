# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime

import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        result = super(StockMove, self)._action_done(cancel_backorder=cancel_backorder)
        result.mapped("sale_line_id.order_id").check_delivered()

        return result

    def _action_cancel(self):
        location_customers = self.env.ref("stock.stock_location_customers")
        from_sale = self.env.context.get("from_sale", False)
        result = True
        if not from_sale:
            result = super(StockMove, self)._action_cancel()
            self.mapped("sale_line_id.order_id").check_delivered()

        def not_cancelled_filter(m):
            return m.state not in ["cancel"] and m.location_dest_id == location_customers

        delivery_cancelled_moves = self.filtered(lambda m: m.location_dest_id == location_customers)

        if not self.env.context.get("disable_sale_cancel", False) and delivery_cancelled_moves:
            lines_to_cancel = delivery_cancelled_moves.sale_line_id.filtered(lambda s: len(s.move_ids.filtered(not_cancelled_filter)) == 0)
            lines_to_cancel.action_cancel()

        for delivery_cancelled_move in delivery_cancelled_moves:
            # Already cancelled qty for sale order line
            cancelled_qty = delivery_cancelled_move.sale_line_id.u_cancelled_qty

            delivery_cancelled_move.sale_line_id.u_cancelled_qty = cancelled_qty + delivery_cancelled_move.product_uom_qty
        return result

    def _prepare_procurement_values(self):
        """
        The sale_line_id is not passed to the next move created by a procurement rule in
        default Odoo 14. This method extends _prepare_procurement_values to allow for that.
        Return: dictionary
        """
        values = super()._prepare_procurement_values()
        values["sale_line_id"] = self.sale_line_id.id
        return values

    def _search_picking_for_assignation(self):
        """
        When searching for picking to assign moves too, the picking should have the
        same priority as the sales order that the move is created from
        """
        picking = super(StockMove, self)._search_picking_for_assignation()
        if self.sale_line_id:
            if picking and picking.priority != self.sale_line_id.order_id.priority:
                return self.env['stock.picking']
        return picking

    def _get_new_picking_values(self):
        """
        When creating a picking from a move, the picking should have the same priority
        as sales order from which it is created.
        """
        values = super(StockMove, self)._get_new_picking_values()
        if len(self.sale_line_id.order_id) == 1:
            # Update the values dictionary with the priority of the associated sale order
            values.update({"priority": self.sale_line_id.order_id.priority})
        return values

    def reduce_product_qty(self, qty):
        """
        Increase cancelled qty on sale order line when we reduce stock move qty from move cancel propagation.
        """
        location_customers = self.env.ref("stock.stock_location_customers")
        result = super().reduce_product_qty(qty)
        if self.sale_line_id and self.location_dest_id == location_customers:
            cancelled_qty = self.sale_line_id.u_cancelled_qty
            self.sale_line_id.u_cancelled_qty = cancelled_qty + qty
        return result
