from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockPickingMarkTodo(models.TransientModel):
    _name = "stock.picking.mark.todo"
    _description = "Mark Transfers as Todo Wizard"

    draft_picking_ids = fields.Many2many(
        "stock.picking", string="Draft Pickings", domain=[("state", "=", "draft")]
    )

    non_draft_picking_ids = fields.Many2many(
        "stock.picking",
        string="Non-Draft Pickings",
        domain=[("state", "!=", "draft")],
        readonly=True,
    )

    has_non_draft_pickings = fields.Boolean(
        "Has Non-Draft Pickings?", compute="_compute_has_non_draft_pickings"
    )

    @api.model
    def default_get(self, fields):
        """Override default get to set values of draft and unaffected pickings

        Args:
            fields_list (list): list of fields

        Returns:
            dict: Returns fields dictionary with values
        """
        Picking = self.env["stock.picking"]
        res = super().default_get(fields)

        picking_ids = self._context.get("active_ids", [])
        draft_picking_ids = Picking.search([("state", "=", "draft"), ("id", "in", picking_ids)]).ids

        non_draft_picking_ids = list(set(picking_ids) - set(draft_picking_ids))
        res.update(
            {"draft_picking_ids": draft_picking_ids, "non_draft_picking_ids": non_draft_picking_ids}
        )
        return res

    @api.depends("non_draft_picking_ids")
    def _compute_has_non_draft_pickings(self):
        """
        For each wizard in self, set True if the wizard contains non-draft Picking records,
        otherwise False
        """
        for wiz in self:
            wiz.has_non_draft_pickings = bool(wiz.non_draft_picking_ids)

    def action_mark_todo(self):
        """Update draft pickings to waiting state"""
        self.ensure_one()
        draft_picking_ids = self.draft_picking_ids.ids
        if not draft_picking_ids:
            raise UserError(_("No draft picking specified"))

        self.draft_picking_ids.action_confirm()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pickings Marked as Todo"),
            "res_model": "stock.picking",
            "view_type": "form",
            "view_mode": "tree,form",
            "domain": [("id", "in", draft_picking_ids)],
        }
