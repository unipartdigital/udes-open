# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons import decimal_precision as dp
from odoo.osv import expression


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

    def action_check(self):
        """Override to update Parent Package on Package if needed."""
        inventories_to_check = self.filtered(lambda i: i.state not in ("done", "cancel"))
        for inventory in inventories_to_check:
            inventory.line_ids._update_package_parent()
        return super(StockInventory, self).action_check()

    def _is_adjusting_reserved(self):
        """Check if a user is adjusting reserved stock."""
        self.ensure_one()
        for line in self.line_ids:
            if line.reserved_qty and line.theoretical_qty != line.product_qty:
                return True
        return False

    def _get_filter(self):
        """
        Returns a dictionary with the following values based on how Inventory record is setup:

        * filter_domain - a search domain (list) for identifying relevant quant records
        * products_to_filter - a recordset of Products that match either match the specified product 
                               or are a child of the specified category
        """
        Product = self.env["product.product"]

        filter_domain = [("location_id", "child_of", self.location_id.id)]
        products_to_filter = Product.browse()

        # case 1: Filter on One owner only or One product for a specific owner
        if self.partner_id:
            partner_domain = [("owner_id", "=", self.partner_id.id)]
            filter_domain = expression.AND([filter_domain, partner_domain])

        # case 2: Filter on One Lot/Serial Number
        if self.lot_id:
            lot_domain = [("lot_id", "=", self.lot_id.id)]
            filter_domain = expression.AND([filter_domain, lot_domain])

        # case 3: Filter on One product
        if self.product_id:
            products_to_filter |= self.product_id

            product_domain = [("product_id", "=", self.product_id.id)]
            filter_domain = expression.AND([filter_domain, product_domain])

        # case 4: Filter on A Pack
        if self.package_id:
            package_domain = [("package_id", "=", self.package_id.id)]
            filter_domain = expression.AND([filter_domain, package_domain])

        # case 5: Filter on One product category + Exhausted Products
        if self.category_id:
            category_products = Product.search([("categ_id", "=", self.category_id.id)])
            products_to_filter |= category_products

            product_category_domain = [("product_id", "in", category_products.mapped("id"))]
            filter_domain = expression.AND([filter_domain, product_category_domain])

        inventory_filter = {
            "filter_domain": filter_domain,
            "products_to_filter": products_to_filter,
        }

        return inventory_filter

    def _get_inventory_lines_values(self):
        """
        Override to refactor logic into separate functions that can be overridden in other modules
        """
        InventoryLine = self.env["stock.inventory.line"]
        Quant = self.env["stock.quant"]
        Product = self.env["product.product"]

        inventory_filter = self._get_filter()

        filter_domain = inventory_filter["filter_domain"]
        products_to_filter = inventory_filter["products_to_filter"]

        quants = Quant.search(filter_domain)
        quant_products = Product.browse()

        quant_dict = {}

        for quant in quants:
            quant_line_vals = InventoryLine._get_quant_line_vals(quant)
            quant_key = InventoryLine._get_quant_key(quant_line_vals)

            # If quant_key already exists, update the current quantity
            if quant_key in quant_dict:
                updated_qty = quant_dict[quant_key]["product_qty"] + quant.quantity
                quant_dict[quant_key]["product_qty"] = updated_qty
                quant_dict[quant_key]["theoretical_qty"] = updated_qty
            else:
                quant_dict[quant_key] = quant_line_vals

            quant_products |= quant.product_id

        vals = list(quant_dict.values())

        if self.exhausted:
            exhausted_vals = self._get_exhausted_inventory_line(products_to_filter, quant_products)
            vals.extend(exhausted_vals)

        return vals

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

    u_result_parent_package_id = fields.Many2one(
        'stock.quant.package', 'Parent Destination Package'
    )

    u_package_parent_package_id = fields.Many2one(
        'stock.quant.package',
        'Current Parent Package',
        help='The current parent package, used to determine if the parent package '
        'on the Inventory Line has been updated'
    )

    u_line_updated = fields.Boolean(
        'Line Updated?',
        compute='_compute_line_updated',
        help='Indicates whether this line has been updated, '
        'which in turn will mean quants are to be adjusted'
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

    @api.multi
    @api.depends(
        'product_qty',
        'theoretical_qty',
        'u_result_parent_package_id',
        'u_package_parent_package_id',
    )
    def _compute_line_updated(self):
        """Apply value of `_get_line_updated` to `u_line_updated` for each line in self"""
        for line in self:
            line.u_line_updated = line._get_line_updated()

    @api.onchange('package_id')
    def onchange_package_id(self):
        """
        Set values for u_result_parent_package_id and u_package_parent_package_id
        when package is changed
        """
        parent_package = self.package_id.package_id
        self.u_result_parent_package_id = parent_package
        self.u_package_parent_package_id = parent_package

    def _get_line_updated(self):
        """Returns True if line quantity or parent package has been updated, otherwise False"""
        self.ensure_one()
        line_updated = False

        if self.product_qty != self.theoretical_qty:
            line_updated = True
        elif self.u_result_parent_package_id != self.u_package_parent_package_id:
            line_updated = True

        return line_updated

    def _get_quants_domain(self):
        """Returns a domain used for retrieving relevant Quant records"""
        return [
            ("company_id", "=", self.company_id.id),
            ("location_id", "=", self.location_id.id),
            ("lot_id", "=", self.prod_lot_id.id),
            ("product_id", "=", self.product_id.id),
            ("owner_id", "=", self.partner_id.id),
            ("package_id", "=", self.package_id.id),
        ]

    def _get_quants(self):
        """
        Override to use domain returned by `_get_quants_domain` which can be easily overriden in 
        other modules, rather than a hard coded search to get relevant Quant records
        """
        Quant = self.env["stock.quant"]
        return Quant.search(self._get_quants_domain())

    def _get_quant_line_vals(self, quant):
        """Returns a dictionary of values used to create Inventory Line from supplied Quant"""
        quant.ensure_one()

        quant_line_vals = {
            "product_id": quant.product_id.id,
            "product_uom_id": quant.product_id.uom_id.id,
            "product_qty": quant.quantity,
            "theoretical_qty": quant.quantity,
            "location_id": quant.location_id.id,
            "prod_lot_id": quant.lot_id.id,
            "package_id": quant.package_id.id,
            "partner_id": quant.owner_id.id,
            "u_result_parent_package_id": quant.package_id.package_id.id,
            "u_package_parent_package_id": quant.package_id.package_id.id,
        }
        return quant_line_vals

    def _get_quant_key(self, quant_line_vals):
        """Generate key used for identifying unique Quant records"""
        quant_key = (
            quant_line_vals["product_id"],
            quant_line_vals["location_id"],
            quant_line_vals["package_id"],
            quant_line_vals["prod_lot_id"],
            quant_line_vals["partner_id"],
        )
        return quant_key

    def _get_move_values(self, qty, location_id, location_dest_id, out):
        """Override to include Parent Package, if set"""
        move_values = super(StockInventoryLine, self)._get_move_values(
            qty, location_id, location_dest_id, out
        )
        move_line_vals = move_values["move_line_ids"][0][2]

        result_parent_package_id = (not out) and self.u_result_parent_package_id.id
        move_line_vals["u_result_parent_package_id"] = result_parent_package_id
        return move_values

    def _update_package_parent(self):
        """Update Package's Parent Package if it has been updated on the Inventory Line"""
        for line in self.filtered(
            lambda l: l.package_id and l.u_result_parent_package_id != l.u_package_parent_package_id
        ):
            line.package_id.sudo().write({"package_id": line.u_result_parent_package_id.id})

    @api.constrains("package_id", "u_result_parent_package_id")
    def _parent_package_check(self):
        """Remove `u_result_parent_package_id` if `package_id` not set"""
        lines_to_update = self.filtered(lambda l: not l.package_id and l.u_result_parent_package_id)
        lines_to_update.write({"u_result_parent_package_id": False})
