from .refactor import Refactor


class GroupByMoveKey(Refactor):
    """
    Group the moves by the splitting criteria.
    For each resulting group of stock moves:
        - Create a new picking
        - Attach the moves to the new picking
    """

    @classmethod
    def name(cls):
        """Set code name of the refactor action."""
        return "group_by_move_key"

    @classmethod
    def description(cls):
        """Set description of the refactor action."""
        return "Group by Move Key"

    def do_refactor(self, moves):
        """
        Ensure that move records only have 1 picking type.
        If a move key format is set carry out the refactor
        by move groups.
        """
        picking_type = moves.picking_type_id
        picking_type.ensure_one()

        if not picking_type.u_move_key_format:
            return moves

        group_by_key = moves.group_by_key()

        return moves.refactor_by_move_groups(group_by_key)
