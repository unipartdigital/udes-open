from odoo import models

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def warn_picking_any_previous_pickings_not_complete_sale(self):
        """Return a warning string when not all pickings have progressed
        to the same picking type or later.

        Determine if this is the case by examining if all picking of the same picking type are
        assigned, done or cancelled.
        """
        accepted_states = ["assigned", "done", "cancel"]
        all_pickings = self.mapped("move_lines.sale_line_id.order_id.picking_ids")
        pickings = all_pickings.filtered(
            lambda p: p.picking_type_id in self.mapped("picking_type_id")
        )
        unaccepted_pickings = pickings.filtered(lambda p: p.state not in accepted_states)
        if unaccepted_pickings:
            so_names = unaccepted_pickings.mapped("move_lines.sale_line_id.order_id.name")
            return f"Sale Order(s) {''.join(so_names)} have incomplete pickings in previous stages."
        else:
            return False

    def add_more_pickings_to_reserve(self, picking_type):
        """
        Extend pickings by inheriting with super, to add more pickings depending on picking type configurations
        """
        pickings = super().add_more_pickings_to_reserve(picking_type)
        if picking_type.u_full_sale_reservation:
            # Adding more pickings and not overriding to make sure that if pickings are not linked with sale orders.
            pickings |= pickings.move_lines.sale_line_id.order_id.picking_ids.filtered(
                lambda p: p.picking_type_id.u_full_sale_reservation and p.state == "confirmed"
            )
        return pickings
