# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def ensure_not_reserved(self):
        """Ensure all quants in the recordset are unreserved."""
        reserved = self.filtered(lambda q: q.reserved_quantity > 0)
        if reserved:
            raise ValidationError(_('Items are reserved and cannot be moved. '
                                    'Please speak to a team leader to resolve '
                                    'the issue.\nAffected Items: %s') % (
                                        ' '.join(reserved.mapped('package_id.name'))
                                        if reserved.mapped('package_id')
                                        else ' '.join(reserved.mapped('product_id.display_name'))))

    def ensure_entire_packages(self):
        """Ensure the recordset self contains all the quants in package present
        in the recordset."""
        packages = self.mapped('package_id')
        package_quant_ids = packages.mapped('quant_ids')

        diff = package_quant_ids - self
        if diff:
            prob_packs = diff.mapped('package_id')
            raise ValidationError(_('Not all quants have been taken.\n'
                                    'Incomplete Packages:\n'
                                    '%s') % (' '.join(prob_packs.mapped('name'))))

    def ensure_valid_location(self, location_id):
        """ Ensure the recorset self contains quants child of location_id
        """
        # TODO: check this function again, create generic is_valid/are_valid?
        Location = self.env['stock.location']
        n_quant_locs = len(self.mapped('location_id'))
        child_locs = Location.search([
                ('id', 'child_of', location_id),
                ('id', 'in', self.mapped('location_id.id'))
            ])
        if len(child_locs) != n_quant_locs:
            raise ValidationError(
                    _('The locations of some quants are not children of'
                      ' location %s') %
                        Location.browse(location_id).name)

    def _gather(self, product_id, location_id, **kwargs):
        """ Call default _gather function, if quant_ids context variable
            is set the resulting quants are filtered by id.

            Context variable quant_ids might contain quants of different products.
        """
        quants = super(StockQuant, self)._gather(product_id, location_id, **kwargs)
        quant_ids = self.env.context.get('quant_ids')
        if quant_ids:
            quants = quants.filtered(lambda q: q.id in quant_ids)
        return quants

    @api.multi
    def total_quantity(self):
        """ Returns the total quantity of the quants in self
        """
        return sum(self.mapped('quantity'))

    @api.multi
    def group_quantity_by_product(self):
        """ Returns a dictionary with the total quantity per product,
            mapped by product_id.
        """
        products = {}
        for quant in self:
            products.setdefault(quant.product_id.id, 0)
            products[quant.product_id.id] += quant.quantity
        return products
