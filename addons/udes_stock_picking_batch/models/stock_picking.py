from odoo import models, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.constrains("batch_id")
    def _trigger_batch_confirm_and_remove(self):
        """
       Batch may require new pickings to be auto confirmed or removed
       Note: this function is very fragile, any change might brake its functionality
        """
        origin_batches = self.env.context.get("orig_batches")
        batches = self.batch_id
        if origin_batches:
            batches += origin_batches
        batches._assign_picks()
        batches._remove_unready_picks()
        batches._compute_state()

    @api.constrains("state")
    def _trigger_batch_state_recompute(self):
        """
        Changes to picking state cause batch state recompute, may also cause
        unready pickings to be removed from the batch
        Note: this function is very fragile, any change might brake its functionality
        """
        origin_batches = self.env.context.get("orig_batches")
        batches = self.batch_id
        if origin_batches:
            batches += origin_batches
        batches._remove_unready_picks()
        batches._compute_state()

    def action_assign(self):
        """
        Recompute batch state. In theory this is not necessary
        but the constraint on state has not proven to work correctly.
        """
        super(StockPicking, self).action_assign()
        self.batch_id._compute_state()

    def write(self, vals):
        """
        If writing picking, check if previous batch is now complete.
        This will be used to trigger recompute of the batch state
        we can't relate on the state after as batch_id might be
        removed during write.
        """

        if self.batch_id:
            self = self.with_context(orig_batches=self.batch_id)
        return super(StockPicking, self).write(vals)
