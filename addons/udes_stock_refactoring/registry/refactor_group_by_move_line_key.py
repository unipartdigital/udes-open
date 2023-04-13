from .refactor import Refactor


class GroupByMoveLineKey(Refactor):
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
        return "group_by_move_line_key"

    @classmethod
    def description(cls):
        """Set description of the refactor action."""
        return "Group by Move Line Key"

    def do_refactor(self, moves):
        """
        Ensure that move records only have 1 picking type.
        If a move line key format is set carry out the refactor
        by move line groups.
        """
        picking_type = moves.picking_type_id
        picking_type.ensure_one()

        if not picking_type.u_move_line_key_format:
            return moves

        group_by_key = moves.move_line_ids.group_by_key()

        return moves.refactor_by_move_line_groups(group_by_key.items())
