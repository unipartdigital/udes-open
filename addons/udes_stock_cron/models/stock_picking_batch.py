# -*- coding: utf-8 -*-
from odoo import models, api
import logging
_logger = logging.getLogger(__name__)

class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

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