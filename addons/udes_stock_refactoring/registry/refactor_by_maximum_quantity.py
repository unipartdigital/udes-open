from .refactor import Refactor


class ByMaximumQuantity(Refactor):
    """
    Group the move lines by the splitting criteria.
    For each resulting group of stock move lines:
        - Create a new picking
        - Split any stock move records that are only
          partially covered by the group of stock moves
        - Attach the moves and move lines to the new picking
    """

    @classmethod
    def name(cls):
        """Set code name of the refactor action."""
        return "by_maximum_quantity"

    @classmethod
    def description(cls):
        """Set description of the refactor action."""
        return "By Maximum Quantity"

    def do_refactor(self, moves):
        """
        Ensure that move records only have 1 picking type.
        If picking type assign refactor constraint value is set to a value greater or equal than 1
        carry out the refactor by its value.
        """
        picking_type = moves.picking_type_id
        picking_type.ensure_one()

        if picking_type.u_assign_refactor_constraint_value < 1:
            return moves

        return moves._refactor_action_by_maximum_quantity(
            picking_type.u_assign_refactor_constraint_value
        )
