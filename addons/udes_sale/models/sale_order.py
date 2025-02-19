from odoo import models, api, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    NON_NEGATIVE_FIELDS = [
        "price_unit",
        "product_uom_qty",
    ]

    @api.constrains(*NON_NEGATIVE_FIELDS)
    def _constrain_non_negative_values(self):
        for record in self:
            for field in record.NON_NEGATIVE_FIELDS:
                if getattr(record, field) < 0:
                    raise UserError(
                        _("Negative values for %s on %s are not allowed")
                        % (field, record.order_id.name)
                    )
