from .refactor import Refactor


class BatchPickingsByDate(Refactor):
    """Refactor pickings by scheduled date."""

    @classmethod
    def name(cls):
        """Set code name of the refactor action."""
        return "batch_pickings_by_date"

    @classmethod
    def description(cls):
        """Set description of the refactor action."""
        return "Batch Pickings by Date"

    def do_refactor(self, moves):
        """Batch pickings by date."""
        return moves._refactor_action_batch_pickings_by(
            lambda picking: (picking.scheduled_date.strftime("%Y-%m-%d"))
        )
