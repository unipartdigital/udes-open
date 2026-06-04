from odoo import models, fields


class StockQuantityHistory(models.TransientModel):
    _inherit = "stock.quantity.history"

    def open_at_date(self):
        res = super().open_at_date()
        if (ctx := res.get("context")) and "to_date" in ctx:
            ctx.update({"to_date": fields.Datetime.to_string(ctx.get("to_date"))})
        return res
