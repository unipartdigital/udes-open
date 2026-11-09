from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_blocked_reservation_groups(self):
        """
        Extend to move the move lines of picking types with u_full_sale_reservation to
        full_reservation when blocking, adding the pickings of their sale orders with the same
        configuration to full_reservation_pickings, as they are reserved together

        The sale orders are found from the pickings already reserved together too, e.g. the
        pickings of a batch reserved atomically, as add_more_pickings_to_reserve does
        """
        groups = super()._get_blocked_reservation_groups()
        sale_move_lines = (groups["unreservable"] | groups["full_reservation"]).filtered(
            lambda ml: ml.move_id.sale_line_id
            and ml.picking_id.picking_type_id.u_full_sale_reservation
        )
        groups["unreservable"] -= sale_move_lines
        groups["full_reservation"] |= sale_move_lines
        sale_pickings = (groups["full_reservation_pickings"] | sale_move_lines.picking_id).filtered(
            lambda p: p.picking_type_id.u_full_sale_reservation
        )
        groups["full_reservation_pickings"] |= (
            sale_pickings.move_lines.sale_line_id.order_id.picking_ids.filtered(
                lambda p: p.picking_type_id.u_full_sale_reservation
            )
        )
        return groups
