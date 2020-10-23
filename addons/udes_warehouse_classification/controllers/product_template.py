from odoo import http, _
from odoo.http import request


class ControllerProductClassifications(http.Controller):
    @http.route(
        "/api/product-product/get_product_classifications/",
        type="json",
        methods=["GET"],
        auth="user",
    )
    def get_classification_messages_for_product_picking(
        self, product_barcode, picking_type_id=None
    ):
        """ Search for product classification messages by product barcode and picking type
            returns the messages which match the given criteria.

            @param product_barcode
                This is a string that entirely matches the barcode
            @param picking_type_id (optional)
                This is the string for the current picking type

        """
        Product = request.env["product.product"]
        product = Product.get_product(product_barcode)
        product_classifications = product.u_product_warehouse_classification_ids

        if not picking_type_id:
            classifications = product_classifications

        else:
            classifications = product_classifications.filtered(
                lambda c: picking_type_id in c.picking_type_ids.mapped("id")
            )

        return [
            {"message": message}
            for message in classifications.sorted("sequence").mapped("alert_message")
        ]
