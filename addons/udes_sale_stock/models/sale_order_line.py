"""Sale order line"""

from datetime import datetime

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_cancelled = fields.Boolean(string="Cancelled", readonly=True, default=False, index=True)
    ui_is_cancelled = fields.Boolean(
        string="Cancelled", compute="_get_ui_is_cancelled", inverse="_set_ui_is_cancelled"
    )
    cancel_date = fields.Datetime(
        string="Cancel Date", help="Time of cancellation", readonly=True, index=True
    )
    is_cancelled_due_shortage = fields.Boolean(
        string="Cancelled due to a Shortage",
        help="Whether the sale order line was cancelled due to a stock shortage",
        default=False,
        index=True,
    )

    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id)
        values.update(
            {"priority": self.order_id.priority,}
        )
        return values

    def action_cancel(self):
        """ A cancelled SO line will also cancel move IDs """
        to_cancel = self.filtered(lambda l: not l.is_cancelled)

        if not to_cancel:
            return False

        now_date = datetime.now()
        cancel_vals = {
            "is_cancelled": True,
            "cancel_date": fields.Datetime.to_string(now_date),
            "is_cancelled_due_shortage": self.env.context.get("cancelled_stock_shortage", False),
        }
        to_cancel.write(cancel_vals)

        to_cancel.mapped("move_ids").filtered(
            lambda m: m.state not in ("done", "cancel")
        )._action_cancel()
        to_cancel.mapped("order_id").check_state_cancelled()

    def _action_launch_procurement_rule(self):
        not_cancelled_lines = self.filtered(lambda l: not l.is_cancelled)
        super(SaleOrderLine, not_cancelled_lines)._action_launch_procurement_rule()

    @api.depends("is_cancelled")
    def _get_ui_is_cancelled(self):
        """Populates the `ui_is_cancelled` field"""
        for line in self:
            line.ui_is_cancelled = line.is_cancelled

    def _set_ui_is_cancelled(self):
        """Triggers cancellation of sale order lines from the UI"""
        lines_to_uncancel = self.filtered(lambda l: l.is_cancelled and not l.ui_is_cancelled)
        lines_to_cancel = self.filtered(lambda l: not l.is_cancelled and l.ui_is_cancelled)

        # Check if the warehouse config allow manual cancellation
        if lines_to_cancel and False in self.mapped(
            "order_id.warehouse_id.u_allow_manual_sale_order_line_cancellation"
        ):
            raise ValidationError(
                _(
                    "Manual cancellation of individual order lines is not "
                    "allowed by the warehouse config"
                )
            )

        # Forbid uncancellation of sale order lines
        if lines_to_uncancel:
            raise ValidationError(
                _("Cannot uncancel order lines: %s")
                % (", ".join(lines_to_uncancel.mapped("name")),)
            )

        # Forbid cancellation of completed sale order lines
        lines_done = lines_to_cancel.filtered(lambda l: l.state == "done")
        if lines_done:
            raise ValidationError(
                _("Cannot cancel completed order lines: %s")
                % (", ".join(lines_done.mapped("name")),)
            )

        # Forbid cancellation of sale order lines with stock.pickings in progress
        # Cancellation of sale order lines with the part of the outbound
        # process completed and the next part unstarted is intentionally
        # allowed. In this case it is up to the users to stock move products
        # back into stock.
        moves = lines_to_cancel.mapped("move_ids")
        in_progress_moves = moves.filtered(
            # Sale order lines are in progress if any of their pickings in the route are in progress
            lambda m: m.state not in ("done", "cancel")
            and (
                m.picking_id.batch_id.state == "in_progress"
                # NB: `picking_id.move_lines` is not necessarily a subset of `moves`
                or m.picking_id.move_lines.filtered(lambda m2: m2.quantity_done > 0)
            )
        )
        in_progress_lines = in_progress_moves.mapped("sale_line_id")
        if in_progress_lines:
            raise ValidationError(
                _("Cannot cancel order lines with pickings in progress: %s")
                % (", ".join(in_progress_lines.mapped("name")),)
            )

        # Disallow cancellation at certain stages in the outbound process
        # NB: If half of a sale order line has left the warehouse and the other
        #     half has not been picked yet, cancellation should be allowed.
        uncancellable_moves = moves.filtered(
            lambda m: m.state in ("partially_available", "assigned")
            and m.picking_id.picking_type_id
            in m.sale_line_id.order_id.warehouse_id.u_disallow_manual_sale_order_line_cancellation_at_picking_type_ids
            # move.warehouse_id can't be used as it is not populated
        )

        uncancellable_lines = uncancellable_moves.mapped("sale_line_id")
        if uncancellable_lines:
            raise ValidationError(
                _("Cannot cancel order lines with pickings at the %s stage: %s")
                % (
                    "/".join(uncancellable_moves.mapped("picking_type_id.name")),
                    ", ".join(uncancellable_lines.mapped("name")),
                )
            )

        lines_to_cancel.action_cancel()
