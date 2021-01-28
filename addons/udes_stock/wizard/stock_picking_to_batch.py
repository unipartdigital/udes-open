import logging
from odoo import api, fields, models
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class StockPickingToBatch(models.TransientModel):
    _inherit = "stock.picking.to.batch"

    msg = fields.Char()
    is_diff_priority = fields.Boolean(default=False)
    confirm_add_picking = fields.Boolean(
        string="Tick to Confirm",
        default=False,
        help="Confirm the difference between batch and picking priority and add to batch",
    )

    @api.multi
    @api.onchange("batch_id")
    def onchange_batch_id(self):
        self.ensure_one()
        self.msg = ""
        self.is_diff_priority = False
        warehouse = self.env.user.get_user_warehouse()
        u_log_batch_picking = warehouse.u_log_batch_picking
        if self.batch_id and u_log_batch_picking:
            Picking = self.env["stock.picking"]
            pickings = Picking.browse(self.env.context.get("active_ids"))
            diff_priority_pickings = self.batch_id.check_same_picking_priority(
                pickings, mode="desktop"
            )
            if diff_priority_pickings:
                self.msg = _(
                    "Selected pickings %s have different priorities than batch priority. "
                    "Do you wish to continue?"
                ) % (diff_priority_pickings)
                self.is_diff_priority = True
