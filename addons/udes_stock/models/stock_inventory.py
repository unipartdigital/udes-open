# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons import decimal_precision as dp


class StockInventory(models.Model):
    _name = 'stock.inventory'
    _inherit = 'stock.inventory'

    u_preceding_inventory_ids = fields.One2many('stock.inventory',
                                                'u_next_inventory_id',
                                                string='Preceding Inventories',
                                                readonly=True)

    u_next_inventory_id = fields.Many2one('stock.inventory',
                                          'Next inventory',
                                          readonly=True,
                                          index=True)

    @api.multi
    def action_done(self):
        """
        Extends the parent method by ensuring that there are no
        incomplete preceding inventories.

        Also checks that a user is allowed to adjust reserved stock.

        Raises a ValidationError otherwise.
        """
        User = self.env['res.users']

        for prec in self.u_preceding_inventory_ids:
            if prec.state != 'done':
                raise ValidationError(
                    _('There are undone preceding inventories.'))

        if self._is_adjusting_reserved():
            warehouse = User.get_user_warehouse()
            if not (warehouse.u_inventory_adjust_reserved or
                    self.env.user.has_group("udes_security.group_debug_user")):
                raise ValidationError(
                    _("You are not allowed to adjust reserved stock. "
                      "The stock has not been adjusted.")
                )

        return super(StockInventory, self).action_done()

    @api.multi
    def button_done(self):
        """Add a popup to inform a user that they are adjusting reserved stock."""
        self.ensure_one()

        if self._is_adjusting_reserved():
            return {
                'name': _('Adjust Reserved Stock?'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.inventory',
                'views': [(self.env.ref('udes_stock.view_adjust_reserved').id, 'form')],
                'view_id': self.env.ref('udes_stock.view_adjust_reserved').id,
                'target': 'new',
                'res_id': self.id,
                'context': self.env.context,
            }
        else:
            return self.action_done()

    def _is_adjusting_reserved(self):
        """Check if a user is adjusting reserved stock."""
        self.ensure_one()
        for line in self.line_ids:
            if line.reserved_qty and line.theoretical_qty != line.product_qty:
                return True
        return False

    @api.multi
    def write(self, values):
        if 'done' in self.mapped('state'):
            raise UserError(
                _('Cannot write to an adjustment which has already been '
                  'validated'))
        return super(StockInventory, self).write(values)


class StockInventoryLine(models.Model):
    _name = 'stock.inventory.line'
    _inherit = 'stock.inventory.line'

    reserved_qty = fields.Float(
        'Reserved Quantity',
        compute='_compute_reserved_qty',
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True,
        store=False
    )

    @api.one
    @api.depends(
        'location_id',
        'product_id',
        'package_id',
        'product_uom_id',
        'company_id',
        'prod_lot_id',
        'partner_id'
    )
    def _compute_reserved_qty(self):
        """Compute the reserved quantity for the line."""
        reserved_qty = sum([quant.reserved_quantity for quant in self._get_quants()])
        if reserved_qty and self.product_uom_id and self.product_id.uom_id != self.product_uom_id:
            reserved_qty = self.product_id.uom_id._compute_quantity(
                reserved_qty,
                self.product_uom_id
            )
        self.reserved_qty = reserved_qty
