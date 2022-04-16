from odoo import models, fields, _, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    picking_type_ids = fields.Many2many(
        "stock.picking.type",
        string="Operation Types",
        compute="_compute_picking_type",
        store=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        states={
            "draft": [("readonly", False)],
            "waiting": [("readonly", False)],
            "ready": [("readonly", False)],
            "in_progress": [("readonly", False)],
        },
    )
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

    @api.depends("picking_ids", "picking_ids.picking_type_id")
    def _compute_picking_type(self):
        for batch in self:
            if batch.picking_ids:
                batch.picking_type_ids = batch.picking_ids.mapped("picking_type_id")
            elif not isinstance(batch.id, models.NewId):
                # If the picking ids are empty use the stored picking type ids
                batch.picking_type_ids = batch.read(["picking_type_ids"])[0]["picking_type_ids"]

    def _remove_unready_picks(self):
        """ Remove unready picks from running batches in self, if configured """
        if self.env.context.get("lock_batch_state"):
            # State is locked so don't do anything
            return

        # Get unready picks in running batches
        unready_picks = self.filtered(
            lambda b: b.state in ["waiting", "in_progress"]
        ).unready_picks()

        if not unready_picks:
            # Nothing to do
            return

        # Remove unready pick, if configured.
        # unready_picks.filtered(lambda p: p.picking_type_id.u_remove_unready_batch).write(
        #     {"batch_id": False, "u_reserved_pallet": False}
        # )
        unready_picks.filtered(lambda p: p.picking_type_id.u_remove_unready_batch).write(
            {"batch_id": False}
        )

    @api.constrains("picking_ids")
    def _assign_picks(self):
        """If configured, attempt to assign all the relevant pickings in self"""
        if self.env.context.get("lock_batch_state"):
            # State is locked so don't do anything
            return

        # Get active batches with pickings
        batches = self.filtered(
            lambda b: (
                b.state in ["waiting", "in_progress"]
                and b.picking_ids
                and any(b.mapped("picking_type_ids.u_auto_assign_batch_pick"))
            )
        )

        for batch in batches:
            picks_to_assign = batch.picking_ids.filtered(
                lambda p: p.state == "confirmed"
                and p.picking_type_id.u_auto_assign_batch_pick
                and p.mapped("move_lines").filtered(
                    lambda move: move.state not in ("draft", "cancel", "done")
                )
            )
            if picks_to_assign:
                picks_to_assign.with_context(lock_batch_state=True).action_assign()
                picks_to_assign.batch_id._compute_state()

    def _compute_state_depends_fields(self):
        return []

    # We do not use api.depends() as we micromanage when to recompute the state of the batch
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
        picks = self.picking_ids
        return picks.filtered(lambda pick: pick.state in ["done", "cancel"])

    def ready_picks(self):
        """ Return ready picks from picks or self.picking_ids """
        picks = self.picking_ids
        return picks.filtered(lambda pick: pick.state == "assigned")

    def unready_picks(self):
        """ Return unready picks from picks or self.picking_ids """
        picks = self.picking_ids
        return picks.filtered(lambda pick: pick.state in ["draft", "waiting", "confirmed"])

    def mark_as_todo(self):
        """Changes state from draft to waiting.

        This is done without calling action assign.
        """
        _logger.info("User %r has marked %r as todo.", self.env.uid, self)
        not_draft = self.filtered(lambda b: b.state != "draft")
        if not_draft:
            raise UserError(
                _(
                    "The following batches can not be marked as Todo as they are not in the draft state: %s"
                )
                % not_draft.mapped("name")
            )
        self.write({"state": "waiting"})
        self._compute_state()

    def confirm_picking(self):
        """Overwrite method confirm picking to raise error if not in draft and
           rollback to draft on error in action_assign.
        """
        if any(batch.state != "draft" for batch in self):
            raise ValidationError(
                _("Batch (%s) is not in state draft can not perform " "confirm_picking")
                % ",".join(b.name for b in self if b.state != "draft")
            )

        pickings_todo = self.mapped("picking_ids")
        self.write({"state": "waiting"})  # Get it out of draft

        try:
            p = pickings_todo.with_context(lock_batch_state=True).action_confirm()
            self._compute_state()

            return p
        except:
            self.write({"state": "draft"})
            raise
