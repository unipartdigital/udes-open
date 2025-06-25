from odoo.addons.udes_stock.tests.common import BaseUDES


class BaseSaleUDES(BaseUDES):
    """
    Creating a BaseSaleUDES testing class on top of BaseUDES which we can reuse when we need to have BaseUDES with
    some helper methods related with sale order.
    """

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
    def create_sale(cls, customer, client_order_ref, requested_date, **kwargs):
        """Create a sale order"""
        create_values = {
            "partner_id": customer.id,
            "partner_invoice_id": customer.id,
            "partner_shipping_id": customer.id,
            "pricelist_id": cls.env.ref("product.list0").id,
            "client_order_ref": client_order_ref,
            "requested_date": requested_date,
        }
        create_values.update(kwargs)
        return cls.env["sale.order"].create(create_values)

    @classmethod
    def complete_sale(cls, sale):
        """Complete a sale by completing its pickings."""
        pickings = sale.picking_ids
        picks_to_process = pickings.filtered(lambda p: not p.u_prev_picking_ids)
        while picks_to_process:
            picks_to_process.action_assign()
            for picking in picks_to_process:
                cls.complete_picking(picking)
            picks_to_process = picks_to_process.u_next_picking_ids
