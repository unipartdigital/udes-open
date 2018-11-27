from odoo import api, fields, models,  _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_done(self):
        """ Override action_done """
        self.validate_expiry_dates()
        return super(StockPicking, self).action_done()

    def validate_expiry_dates(self):
        """ Validate expiry dates for all move lines in self based on picking and product config """
        for line in self.mapped('move_line_ids').filtered(
                lambda ml: ml.picking_id.picking_type_id.u_confirm_expiry_date):
            if line.product_id.tracking == 'lot' and line.qty_done > 0 and not line.u_expiry_date:
                raise ValidationError(
                    _('Product %s must have an expiry date' % line.product_id.name))
