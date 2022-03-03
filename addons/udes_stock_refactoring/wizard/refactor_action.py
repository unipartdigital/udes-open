from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class StockPickingRefactorCriteria(models.AbstractModel):
    _name = "stock.picking.refactor.criteria"
    _description = "Stock Picking Refactor Criteria"

    refactor_action = fields.Selection(
        selection="get_refactor_actions_for_selection",
        string="Refactor Action",
        help="Choose the custom refactor action to be applied in case of custom refactor",
    )
    custom_criteria = fields.Boolean(
        string="Custom Criteria",
        help="""
            If set to False it will refactor by default criteria which are set on picking types and 
            triggered by appropriate state of the pickings.
            If set to True it will show other options that we may refactor even if is not the 
            specific trigger state
            """,
    )

    @api.model
    def get_refactor_actions_for_selection(self):
        """Finding possible selection values from picking type action trigger selection fields"""
        PickingType = self.env["stock.picking.type"]
        picking_type_fields = PickingType._fields

        action_selection_fields = self.get_action_selection_fields()
        picking_type_action_selection_fields = {
            field_name: picking_type_fields[field_name]
            for field_name in picking_type_fields
            if field_name in action_selection_fields
        }
        actions_for_selection_list = [
            selection_field._description_selection(self.env)
            for selection_field in picking_type_action_selection_fields.values()
        ]
        # Finding set of selection values by excluding duplicates
        actions_for_selection_set = set().union(*actions_for_selection_list)
        return list(actions_for_selection_set)

    @api.model
    def get_action_selection_fields(self):
        """Returning from a method in case that is needed to extend selection fields"""
        return ["u_post_confirm_action", "u_post_assign_action", "u_post_validate_action"]

    @api.onchange("custom_criteria")
    def onchange_custom_criteria(self):
        self.refactor_action = False


class RefactorStockPickingBatch(models.TransientModel):
    _name = "stock.picking.batch.refactor.wizard"
    _inherit = ["stock.picking.refactor.criteria"]
    _description = "Stock Picking Batch Refactor Action"

    def do_refactor(self):
        Batch = self.env["stock.picking.batch"]

        self.ensure_one()
        batch_ids = self.env.context.get("active_ids")

        _logger.info(
            f"User number {str(self.env.uid)} has requested refactoring of batches {batch_ids}"
        )
        batches = Batch.browse(batch_ids)
        res = batches.picking_ids.move_lines._action_refactor(
            refactor_action=self.refactor_action
        )
        batches.picking_ids.unlink_empty()
        return res


class RefactorStockPicking(models.TransientModel):
    _name = "stock.picking.refactor.wizard"
    _inherit = ["stock.picking.refactor.criteria"]
    _description = "Stock Picking Refactor Action"

    def do_refactor(self):
        Picking = self.env["stock.picking"]

        self.ensure_one()
        picking_ids = self.env.context.get("active_ids")

        _logger.info(
            f"User number {str(self.env.uid)} has requested refactoring of pickings {picking_ids}"
        )

        pickings = Picking.browse(picking_ids)
        res = pickings.move_lines._action_refactor(refactor_action=self.refactor_action)
        pickings.unlink_empty()
        return res


class RefactorStockMove(models.TransientModel):
    _name = "stock.move.refactor.wizard"
    _inherit = ["stock.picking.refactor.criteria"]
    _description = "Stock Move Refactor Action"

    def do_refactor(self):
        Move = self.env["stock.move"]

        self.ensure_one()
        move_ids = self.env.context.get("active_ids")

        _logger.info(
            f"User number {str(self.env.uid)} has requested refactoring of moves {move_ids}"
        )

        moves = Move.browse(move_ids)
        pickings_before_refactoring = moves.picking_id
        res = moves._action_refactor(refactor_action=self.refactor_action)
        pickings_before_refactoring.unlink_empty()
        return res
