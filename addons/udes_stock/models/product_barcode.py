from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)


class ProductBarcode(models.Model):
    _name = "product.barcode"
    _inherit = ["mixin.stock.model"]
    _description =  "Product Barcode"
    _order = "name"

    name = fields.Char(
        "Barcode", copy=False, required=True, index=True,
        help="International Article Number used for product identification."
    )
    product_tmpl_id = fields.Many2one("product.template", string="Product", required=True, ondelete="cascade", index=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "A barcode can only be assigned to one product!"),
    ]
