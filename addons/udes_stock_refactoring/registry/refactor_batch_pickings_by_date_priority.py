from .refactor import Refactor


class BatchPickingsByDatePriority(Refactor):
    """Refactor pickings by scheduled date and priority."""

    @classmethod
    def name(cls):
        """Set code name of the refactor action."""
        return "batch_pickings_by_date_priority"

    @classmethod
    def description(cls):
        """Set description of the refactor action."""
        return "Batch Pickings by Date and Priority"

    def do_refactor(self, moves):
        """Batch pickings by date and priority."""
        return moves._refactor_action_batch_pickings_by(
            lambda picking: (picking.scheduled_date.strftime("%Y-%m-%d"), picking.priority)
        )
