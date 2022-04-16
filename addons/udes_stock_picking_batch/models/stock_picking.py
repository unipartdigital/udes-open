from odoo import models, api, fields


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # override batch_id to be copied
    batch_id = fields.Many2one("stock.picking.batch", copy=True)

    # def action_done(self):
    #     """
    #     Ensure we don't incorrectly validate pending pickings.
    #     Check if picking batch is now complete
    #     """
    #     self.assert_not_pending()
    #     mls = self.mapped("move_line_ids")
    #     # Prevent recomputing the batch stat
    #     batches = mls.mapped("picking_id.batch_id")
    #     next_pickings = self.mapped("u_next_picking_ids")
    #
    #     res = super(StockPicking, self.with_context(lock_batch_state=True)).action_done()
    #
    #     # just in case move lines change on action done, for instance cancelling
    #     # a picking
    #     mls = mls.exists()
    #     picks = mls.mapped("picking_id")
    #     # batches of the following stage should also be recomputed
    #     all_picks = picks | picks.mapped("u_next_picking_ids")
    #     all_picks.with_context(lock_batch_state=False)._trigger_batch_state_recompute()
    #
    #     self.assert_not_lot_restricted()
    #
    #     extra_context = {}
    #     if hasattr(self, "get_extra_printing_context"):
    #         extra_context = picks.get_extra_printing_context()
    #
    #     # # Trigger print strategies for pickings done
    #     # self.env.ref("udes_stock.picking_done").with_context(
    #     #     active_model=picks._name,
    #     #     active_ids=picks.ids,
    #     #     action_filter="picking.action_done",
    #     #     **extra_context
    #     # ).run()
    #     if self:
    #         (self | next_pickings).unlink_empty()
    #     return res
    #
    # def action_cancel(self):
    #     """
    #     Check if picking batch is now complete
    #     """
    #     batch = self.mapped("batch_id")
    #     res = super(StockPicking, self.with_context(lock_batch_state=True)).action_cancel()
    #     batch._compute_state()
    #     return res

    # @api.depends("move_type", "move_lines.state", "move_lines.picking_id")
    # def _compute_state(self):
    #     """Prevent pickings to be in state assigned when not able to handle
    #     partials, so they should remain in state waiting or confirmed until
    #     they are fully assigned.
    #
    #     Add the flag 'computing_state' when we call can_handle_partials here to
    #     distinguish it from other calls.
    #     """
    #     for rec in self:
    #         move_lines = rec.move_lines.filtered(lambda move: move.state not in ["cancel", "done"])
    #         # if move_lines and not rec.can_handle_partials(computing_state=True):
    #         if move_lines:
    #             relevant_move_state = move_lines._get_relevant_state_among_moves()
    #             if relevant_move_state == "partially_available":
    #                 if rec.u_prev_picking_ids:
    #                     rec.state = "waiting"
    #                 else:
    #                     rec.state = "confirmed"
    #                 return
    #
    #     super()._compute_state()

    @api.constrains("batch_id")
    def _trigger_batch_confirm_and_remove(self):
        """Batch may require new pickings to be auto confirmed or removed"""
        for batches in self.env.context.get("orig_batches"), self.mapped("batch_id"):
            if batches:
                batches._assign_picks()
                batches._remove_unready_picks()
                batches._compute_state()

    @api.constrains("state")
    def _trigger_batch_state_recompute(self):
        """Changes to picking state cause batch state recompute, may also cause
        unready pickings to be removed from the batch"""
        for batches in self.env.context.get("orig_batches"), self.mapped("batch_id"):
            if batches:
                batches._remove_unready_picks()
                batches._compute_state()

    def write(self, vals):
        """If writing picking, check if previous batch is now complete"""
        # This will be used to trigger recompute of the batch state
        # we can't relate on the state after as batch_id might be
        # removed in the write
        batches = self.mapped(lambda p: p.batch_id)
        context_vals = {"orig_batches": batches} if batches else {}
        return super(StockPicking, self.with_context(**context_vals)).write(vals)
