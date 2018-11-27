from odoo import api, fields, models,  _
from odoo.exceptions import ValidationError


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    u_expiry_date = fields.Date('Expiry date')

    def _prepare_line_product_info(self, ml_values, products_info):
        """ Update move line product info with expiry dates so that they are written """
        product = self.product_id
        info = products_info[product]
        expiry = False
        if 'u_expiry_date' in info:
            expiry = info['u_expiry_date']

        v, info = super(StockMoveLine, self)._prepare_line_product_info(ml_values, products_info)

        if expiry:
            v['u_expiry_date'] = expiry

        return v, info

    def _update_products_info(self, product, products_info, info):
        """ The purpose of this is to remove expiry date info from this function
         to prevent validation errors being thrown in certain cases """
        expiry_date = False
        if 'u_expiry_date' in info:
            expiry_date = info['u_expiry_date']
            del info['u_expiry_date']

        ret = super(StockMoveLine, self)._update_products_info(product, products_info, info)

        # if we have expiry date then
        if expiry_date:
            ret[product]['u_expiry_date'] = expiry_date

        return ret

    @api.constrains('result_package_id', 'u_expiry_date')
    def unique_expiry_date_per_package(self):
        """ Constraint to prevent multiple expiry dates per package """
        
        Users = self.env['res.users']

        warehouse = Users.get_user_warehouse()
        picking_type = warehouse.in_type_id
        in_mls = self.filtered(
            lambda ml: ml.move_id.picking_type_id == picking_type)
        if in_mls:
            # Get all the related move lines
            all_in_mls = in_mls.mapped('picking_id.move_line_ids')
            for package_id, mls in all_in_mls.groupby(
                    lambda ml: ml.result_package_id.id):
                if package_id:
                    if len(set(mls.filtered(lambda ml: ml.u_expiry_date).mapped('u_expiry_date'))) > 1:
                        raise ValidationError(
                            _('Cannot have more than one expiry date per pallet.'))

