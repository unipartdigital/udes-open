from odoo import models, fields, _, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("waiting", "Waiting"),
            ("ready", "Ready"),
            ("in_progress", "Running"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        compute="_compute_state",
        store=True,
    )

    @api.constrains("user_id")
    def _compute_state(self):
        """ Compute the state of a batch post confirm
            waiting     : At least some picks are not ready
            ready       : All picks are in ready state (assigned)
            in_progress : All picks are ready and a user has been assigned
            done        : All picks are complete (in state done or cancel)

            the other two states are draft and cancel are manual
            to transitions from or to the respective state.
        """
        if self.env.context.get("lock_batch_state"):
            # State is locked so don't do anything
            return

        for batch in self:
            if batch.state in ["draft", "cancel"]:
                # Can not do anything with them don't bother trying
                continue

            if batch.picking_ids:

                ready_picks = batch.ready_picks()
                done_picks = batch.done_picks()
                unready_picks = batch.unready_picks()

                # Figure out state
                if ready_picks and not unready_picks:
                    if batch.user_id:
                        batch.state = "in_progress"
                    else:
                        batch.state = "ready"

                if ready_picks and unready_picks:
                    if batch.user_id:
                        batch.state = "in_progress"
                    else:
                        batch.state = "waiting"

                if done_picks and not ready_picks and not unready_picks:
                    batch.state = "done"
            else:
                batch.state = "done"

    def done_picks(self):
        """ Return done picks from picks or self.picking_ids """
        picks = self.mapped("picking_ids")
        return picks.filtered(lambda pick: pick.state in ["done", "cancel"])

    def ready_picks(self):
        """ Return ready picks from picks or self.picking_ids """
        picks = self.mapped("picking_ids")
        return picks.filtered(lambda pick: pick.state == "assigned")

    def unready_picks(self):
        """ Return unready picks from picks or self.picking_ids """
        picks = self.mapped("picking_ids")
        return picks.filtered(lambda pick: pick.state in ["draft", "waiting", "confirmed"])

    def mark_as_todo(self):
        """Changes state from draft to waiting.

        This is done without calling action assign.
        """
        _logger.info("User %r has marked %r as todo.", self.env.uid, self)
        not_draft = self.filtered(lambda b: b.state != "draft")
        if not_draft:
            raise UserError(_('Only draft batches may be marked as "todo": %s') % not_draft.ids)
        self.write({"state": "waiting"})
        self._compute_state()
