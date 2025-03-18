from odoo import models, fields
from collections import defaultdict, namedtuple


class StockPicking(models.Model):
    _inherit = "stock.picking"

    u_from_two_stage_split = fields.Boolean(
        "Two stage split has been initiated",
        copy=False,
        default=False,
        help="Used to track if a picking is a result of a two stage split, "
        "to prevent it from being split multiple times if stock has been unreserved and re-reserved, "
        "as the split occurs on reservation.",
    )

    def should_two_stage_initiate(self):
        """Determines if the picking in self requires two stages."""
        self.ensure_one()
        Location = self.env["stock.location"]
        # When stock gets reserved (and has not been split already)
        if not self.u_from_two_stage_split and self.state == "assigned":
            # We trigger the split to occur if any of the stock has been reserved
            # against any locations requiring two stage. We also check their parents
            # to avoid needing to configure two stage requirements on every individual location.
            # Individual parent configurations are retrieved later in _get_two_stage_configuration_move_line_mapping()
            from_locations = self.move_line_ids.location_id
            two_stage_locations_incl_parents = Location.search_count(
                [
                    ("id", "parent_of", from_locations.ids),
                    ("u_requires_two_stage_when_stock_reserved", "=", True),
                ]
            )
            return bool(two_stage_locations_incl_parents)
        return False

    def _get_two_stage_configuration_move_line_mapping(self):
        """
        Retrieve a mapping of configuration (intermediate location, intermediate location dest, picking type)
        and the respective moves for each unique configuration which require two stages.
        """
        StockMoveLine = self.env["stock.move.line"]
        Location = self.env["stock.location"]

        configuration_move_line_mapping = defaultdict(StockMoveLine.browse)
        for move_line in self.move_line_ids:
            two_stage_locations = Location.search(
                [
                    ("id", "parent_of", move_line.location_id.id),
                    ("u_requires_two_stage_when_stock_reserved", "=", True),
                ]
            )
            config_location = Location.browse()
            if not two_stage_locations:
                # This line isn't reserved for a two stage configured location, it will be left on the original picking
                # while the move lines with two stage configurations get ripped out into new two stage pickings.
                continue
            elif len(two_stage_locations) > 1:
                # We need to determine the location deepest in the tree (itself, or closest parent) to retreieve the configuration,
                # as it is possible to configure a child location with its own two stage configuration override.
                # The easiest way to do this is just get the location with the most amount of parent_path nodes.
                config_location = two_stage_locations.sorted(
                    lambda l: -len(l.parent_path.split("/"))
                )[0]
            else:
                # There is only one matching configuration, so just use it.
                config_location = two_stage_locations

            # Append this move lines to the set of move lines for this configuration set.
            TwoStageConfig = namedtuple(
                "TwoStageConfig",
                ["intermediate_location_id", "intermediate_dest_location_id", "operation_type_id"],
            )
            # This mapping ends up looking something like this: {
            #   (1, 2, 1): stock.move.line(1,2,3),
            #   (1, 3, 1): stock.move.line(4),
            #   (2, 3, 2): stock.move.line(5,6),
            # }
            configuration_move_line_mapping[
                TwoStageConfig(
                    intermediate_location_id=config_location.u_two_stage_intermediate_location.id,
                    # Set the fallbacks to optional configurations here so grouping is simpler.
                    intermediate_dest_location_id=config_location.u_two_stage_intermediate_dest_location.id
                    or self.location_dest_id.id,
                    operation_type_id=config_location.u_two_stage_intermediate_operation_type.id
                    or self.picking_type_id.id,
                )
            ] |= move_line

        return configuration_move_line_mapping

    def initiate_two_stage_split(self):
        """
        Perform all setup to turn a one stage outbound picking to potentially multiple two stage pickings,
        as per configuration of the reserved move lines locations.
        """
        self.ensure_one()
        Picking = self.env["stock.picking"]

        original_priority = self.priority
        original_origin = self.origin
        original_location = self.location_id
        original_partner = self.partner_id

        configuration_move_line_mapping = self._get_two_stage_configuration_move_line_mapping()
        for configuration, move_lines in configuration_move_line_mapping.items():
            # Split the reserved two stage move lines to a backorder. This makes it so that even on partial reservation,
            # only the reserved stock will get split to two stage, which means the remaining stock on the original pick
            # _could_ be reserved in future, and that could be reserved from normal or two stage locations.
            # We also deal with move lines instead of moves as the same product could be reserved
            # in multiple different 2 stage locations with different configurations.
            # backorder_move_lines is close to getting us this functionality, but not appropriate.
            stage_2_pick_vals = {
                "location_id": configuration.intermediate_location_id,
                "location_dest_id": configuration.intermediate_dest_location_id,
                "origin": original_origin,
                "u_from_two_stage_split": True,
            }
            stage_2_pick = self.split_move_lines_to_backorder(move_lines, **stage_2_pick_vals)
            stage_2_pick.move_lines.write(
                {
                    "location_id": configuration.intermediate_location_id,
                    "state": "waiting",
                }
            )
            # sudo() is needed incase the user does not have permission for the intermediate operation type.
            stage_1_pick = Picking.sudo().create(
                {
                    "picking_type_id": configuration.operation_type_id,
                    "location_id": original_location.id,
                    "location_dest_id": configuration.intermediate_location_id,
                    "scheduled_date": fields.Datetime.now(),
                    "priority": original_priority,
                    "origin": original_origin,
                    "partner_id": original_partner.id,
                    "u_from_two_stage_split": True,
                }
            )
            for move in stage_2_pick.move_lines:
                original_moves = move.move_orig_ids
                move.move_orig_ids = [[6, 0, []]]
                stage_1_move = move.copy(
                    default={
                        "location_id": original_location.id,
                        "location_dest_id": configuration.intermediate_location_id,
                        "picking_id": stage_1_pick.id,
                        "picking_type_id": configuration.operation_type_id,
                        "move_dest_ids": [[6, 0, move.ids]],
                        "move_orig_ids": [[6, 0, original_moves.ids]],
                        "state": "assigned",
                    }
                )
                # The move lines that ended up on the stage 2 pick need moving across.
                move_line = move.move_line_ids
                move_line.write(
                    {
                        "picking_id": stage_1_pick.id,
                        "move_id": stage_1_move.id,
                        "location_dest_id": configuration.intermediate_location_id,
                    }
                )
