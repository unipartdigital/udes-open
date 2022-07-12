from odoo import models, api
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        """
        Extend to apply domain restricting products to those set on inventory adjustment,
        if applicable
        """
        restrict_inv_products = self.env.context.get("search_restrict_inv_product_ids")
        if restrict_inv_products:
            # Values passed from client will be formatted as many2many, need to get actual ids
            inv_adjustment_product_ids = restrict_inv_products[0][2]

            # Only apply restriction if inventory adjustment specifies products
            if inv_adjustment_product_ids:
                args = expression.AND([args, [("id", "in", inv_adjustment_product_ids)]])

        return super()._search(
            args,
            offset=offset,
            limit=limit,
            order=order,
            count=count,
            access_rights_uid=access_rights_uid,
        )
