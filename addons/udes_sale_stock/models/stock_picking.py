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

    def get_pallet_move_details_extra_info(self, result, package, container_id=None):
        """Extend to include information from the sale"""
        res = super().get_pallet_move_details_extra_info(result, package, container_id=container_id)
        # Replace the picking name with the sales order name.
        sale = package.get_sale_order()
        res["title"] = f"Order: {sale.name}"
        # This pair should be at the top, hence insert(0), but name should be first, hence inserting afterwards.
        res["extra_summary"].insert(
            0, f"**Customer Address:** \n{sale.partner_id._display_address()}"
        )
        res["extra_summary"].insert(0, f"**Customer Name:** {sale.partner_id.name}")
        res["courier_info"] = {
            "id": sale.u_carrier_id.id,
            "name": sale.u_carrier_id.name,
        }
        if sale.u_comments:
            # Show at the bottom.
            res["extra_summary"].append(f"**Special Instructions:** {sale.u_comments}")
        return res
