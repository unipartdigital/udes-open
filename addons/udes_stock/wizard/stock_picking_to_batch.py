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
        if self.batch_id:
            pickings = self.env["stock.picking"].browse(self.env.context.get("active_ids"))
            diff_priority_pickings = self.batch_id.check_same_picking_priority(pickings)
            if diff_priority_pickings:
                self.msg = _(
                    "Selected pickings %s has different priority than batch priority. "
                    "Do you wish to continue?"
                ) % (diff_priority_pickings)
                self.is_diff_priority = True

