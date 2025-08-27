from odoo import models, fields, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class UdesProactiveReplen(models.TransientModel):
    _name = "udes.proactive.replen"
    _description = "UDES Proactive Replenishment"

    number_replen_moves = fields.Integer(
        "Number of Products",
        default=20,
        help=("Number of products to generate proactive replen moves."),
    )
    replen_percentage = fields.Integer(
        "Replen Percentage above the minimum",
        default=20,
        help=("Percentage quantity above the minimum to trigger proactive replen."),
    )

    def generate_replen_moves(self):
        """Generate replen moves"""
        OrderPoint = self.env["stock.warehouse.orderpoint"]
        Picking = self.env["stock.picking"]
        ProcurementGroup = self.env["procurement.group"]
        Quant = self.env["stock.quant"]
        pickings = Picking.browse()
        picking_type = self.env.ref("udes_stock.picking_type_proactive_replen")
        _logger.info(
            f"User [{self.env.user.id}] started generation of moves for {self.number_replen_moves} "
            f"products under {self.replen_percentage} threshold."
        )

        # Get all order points
        domain = ProcurementGroup._get_orderpoint_domain()
        orderpoints = OrderPoint.with_context(prefetch_fields=False).search(domain)
        _logger.info(f"Found {len(orderpoints)} orderpoints")
        op_todo = {}
        for orderpoint in orderpoints:
            if orderpoint.qty_to_order > 0:
                # This will need a normal replen, so would skip
                continue
            top = orderpoint.product_max_qty - orderpoint.product_min_qty
            if top <= 0:
                continue
            # orderpoint.qty_forecast takes into account both normal replens and proactive replens,
            # therefore "extra" will include them if they exist and a proactive replen won't get
            # created
            extra = orderpoint.qty_forecast - orderpoint.product_min_qty
            percent_above_min = extra / top * 100
            if percent_above_min <= self.replen_percentage:
                op_todo[orderpoint] = percent_above_min

        _logger.info(f"Only {len(op_todo)} orderpoints under the threshold.")

        counter = 0
        for orderpoint, percent_above_min in sorted(
            op_todo.items(), key=lambda x: x[1], reverse=False
        ):
            if counter >= self.number_replen_moves:
                break
            quants = Quant.search(
                [
                    ("location_id", "child_of", picking_type.default_location_src_id.id),
                    ("product_id", "in", orderpoint.product_id.ids),
                ]
            )
            available = quants.get_quantities_by_key(only_available=True)[orderpoint.product_id]
            qty = orderpoint.product_max_qty - orderpoint.qty_forecast
            if not available:
                continue
            if qty > available:
                qty = available
            products_info = [{"product": orderpoint.product_id, "uom_qty": qty}]
            picking = Picking.create_picking(
                picking_type,
                products_info=products_info,
                confirm=True,
                location_dest_id=orderpoint.location_id.id,
                origin=orderpoint.name,
            )
            moves = picking.move_lines._action_assign()
            pickings |= moves.picking_id
            counter += 1

        _logger.info(
            f"Number of pickings created {len(pickings)} for {self.number_replen_moves} products."
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Proactive Replen Moves"),
            "res_model": "stock.picking",
            "res_id": pickings.ids,
            "view_type": "form",
            "view_mode": "tree,form",
            "target": pickings.ids,
            "domain": [("id", "in", pickings.ids)],
        }
