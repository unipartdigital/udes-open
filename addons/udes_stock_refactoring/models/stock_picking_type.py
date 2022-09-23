from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..registry.refactor import get_selection
from ..registry.refactor_batch_pickings_by_date_priority import BatchPickingsByDatePriority
from ..registry.refactor_batch_pickings_by_date import BatchPickingsByDate
from ..registry.refactor_group_by_move_key import GroupByMoveKey
from ..registry.refactor_group_by_move_line_key import GroupByMoveLineKey

POST_CONFIRM_ACTIONS = [
    get_selection(BatchPickingsByDatePriority),
    get_selection(BatchPickingsByDate),
    get_selection(GroupByMoveKey),
]

POST_ASSIGN_ACTIONS = [
    get_selection(GroupByMoveKey),
    get_selection(GroupByMoveLineKey),
]

POST_VALIDATE_ACTIONS = [
    get_selection(GroupByMoveKey),
    get_selection(GroupByMoveLineKey),
]


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_move_line_key_format = fields.Char(
        "Move Line Grouping Key",
        help="A field name on stock.move.line that can be used to group move lines.",
    )
    u_move_key_format = fields.Char(
        "Move Grouping Key",
        help="A field name on stock.move that can be to group move.",
    )
    # Actions are fetched on implementation from Refactor classes
    u_post_confirm_action = fields.Selection(
        selection=POST_CONFIRM_ACTIONS,
        string="Post Confirm Action",
        help="Choose the action to be taken after confirming a picking.",
    )
    u_post_assign_action = fields.Selection(
        selection=POST_ASSIGN_ACTIONS,
        string="Post Assign Action",
        help="Choose the action to be taken after reserving a picking.",
    )
    u_post_validate_action = fields.Selection(
        selection=POST_VALIDATE_ACTIONS,
        string="Post Validate Action",
        help="Choose the action to be taken after validating a picking.",
    )

    @api.constrains("u_move_key_format")
    def _check_move_key_format(self):
        """
        Raise an exception for invalid move key format.

        Move key format
        Children's names must match the package regex.
        """
        StockPickingType = self.env["stock.picking.type"]

        for picking_type in self:
            if not StockPickingType.valid_key_format(picking_type.u_move_key_format, "stock.move"):
                raise UserError(
                    _("Move key format %s isn't set correctly") % (picking_type.u_move_key_format)
                )

    @api.constrains("u_move_line_key_format")
    def _check_move_line_key_format(self):
        StockPickingType = self.env["stock.picking.type"]

        for picking_type in self:
            if not StockPickingType.valid_key_format(
                picking_type.u_move_line_key_format, "stock.move.line"
            ):
                raise UserError(
                    _("Move line key format %s isn't set correctly")
                    % (picking_type.u_move_line_key_format)
                )

    @api.model
    def valid_key_format(self, key_format, model):
        """Validating if key format is in the expected format.
        Returning True if is in expected format, False otherwise.
        """
        StockPickingType = self.env["stock.picking.type"]
        Model = self.env[model]

        if not key_format:
            return True
        try:
            model_vals = StockPickingType.get_fields_from_key_format(key_format)
            if not all(field_name in Model._fields.keys() for field_name in model_vals):
                return False
        except ValueError:
            return False
        return True

    @api.model
    def get_fields_from_key_format(self, format_str):
        return [str[1:-1].split(".")[0] for str in format_str.split(",")]
