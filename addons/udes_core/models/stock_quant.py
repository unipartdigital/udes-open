from odoo import models, fields, _
from odoo.exceptions import ValidationError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def ensure_not_reserved(self):
        """Ensure all quants in the recordset are unreserved."""
        reserved = self.filtered(lambda q: q.reserved_quantity > 0)
        if reserved:
            raise ValidationError(_('Items are reserved and cannot be moved. '
                                    'Please speak to a team leader to resolve '
                                    'the issue.\nAffected Items:') % (
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
