from odoo.addons.udes_stock.tests import common

from datetime import datetime


class BaseSaleUDES(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(BaseSaleUDES, cls).setUpClass()
        cls.customer = cls.env.ref("base.public_partner")

    @classmethod
    def create_sale_line(cls, sale, product, qty, **kwargs):
        """Create a sale order line and attach it a sale order"""
        create_values = {
            "name": product.name,
            "order_id": sale.id,
            "product_id": product.id,
            "product_uom_qty": qty,
            "product_uom": product.uom_id.id,
            "price_unit": product.list_price,
        }
        create_values.update(kwargs)
        return cls.env["sale.order.line"].create(create_values)

    @classmethod
    def create_sale(cls, customer, **kwargs):
        """Create a sale order"""
        create_values = {
            "partner_id": customer.id,
            "partner_invoice_id": customer.id,
            "partner_shipping_id": customer.id,
            "pricelist_id": cls.env.ref("product.list0").id,
            "client_order_ref": "Test",
            "requested_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        create_values.update(kwargs)
        return cls.env["sale.order"].create(create_values)
