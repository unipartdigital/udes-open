"""Sale order line"""

from datetime import datetime

from odoo import api, models, fields


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_cancelled = fields.Boolean(string="Cancelled", readonly=True, default=False, index=True)
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
