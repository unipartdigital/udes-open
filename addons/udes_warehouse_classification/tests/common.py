# -*- coding: utf-8 -*-

from odoo.tests import common


@common.at_install(False)
@common.post_install(True)
class Base(common.SavepointCase):
    """Defines helper methods without automatic warehouse setup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Reports
        cls.report_a = cls.create_report(
            name="report_a", report_name="report_a", model="product.template"
        )
        cls.report_b = cls.create_report(
            name="report_b", report_name="report_b", model="product.template"
        )

        # Picking types
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

        # Classifications
        cls.inbound_report_a_classification = cls.create_classification(
            name="inbound_report_a",
            alert_message="Inbound, Report a, Alert",
            report_message="Inbound, Report a, Report",
            picking_types=cls.picking_type_in,
            report_types=cls.report_a,
        )
        cls.report_a_classification = cls.create_classification(
            name="report_a", report_message="Report a Report", report_types=cls.report_a
        )
        cls.inbound_alert_classification = cls.create_classification(
            name="inbound_alert", alert_message="Inbound Alert", picking_types=cls.picking_type_in
        )
        cls.outbound_alert_classification = cls.create_classification(
            name="outbound_alert",
            alert_message="Outbound Alert",
            picking_types=cls.picking_type_out,
        )
        cls.report_b_classification = cls.create_classification(
            name="report_b", report_message="Report b Report", report_types=cls.report_b
        )

        # Products
        cls.apple = cls.create_product("Apple")  # no classifications
        cls.banana = cls.create_product(
            "Banana", classifications=cls.inbound_report_a_classification
        )  # classifications = inbound report a
        cls.cherry = cls.create_product(
            "Cherry",
            classifications=cls.inbound_report_a_classification + cls.report_a_classification,
        )  # classifications = inbound report a, report a
        cls.damson = cls.create_product(
            "Damson", classifications=cls.inbound_alert_classification
        )  # classifications = inbound alert a
        cls.elderberry = cls.create_product(
            "Elderberry",
            classifications=cls.inbound_report_a_classification + cls.inbound_alert_classification,
        )  # classifications = inbound report a, inbound alert a
        cls.fig = cls.create_product(
            "Fig",
            classifications=cls.outbound_alert_classification + cls.inbound_alert_classification,
        )  # classifications = outbound and inbound
        cls.grape = cls.create_product(
            "Grape", classifications=cls.outbound_alert_classification + cls.report_b_classification
        )  # classifications = outbound, report b
        cls.honeydew = cls.create_product(
            "Honeydew", classifications=cls.report_a_classification + cls.report_b_classification
        )  # classifications = report a, report b

    @classmethod
    def create_product(cls, name, classifications=False, **kwargs):
        """ Create and return a product."""
        Product = cls.env["product.product"]
        vals = {
            "name": "Test product {}".format(name),
            "barcode": "product{}".format(name),
            "default_code": "product{}".format(name),
            "type": "product",
            "u_product_warehouse_classification_ids": [(6, 0, classifications.mapped("id"))]
            if classifications
            else False,
        }
        vals.update(kwargs)
        return Product.create(vals)

    @classmethod
    def create_move(cls, product, qty, picking, **kwargs):
        """ Create and return a move for the given product and qty."""
        Move = cls.env["stock.move"]
        vals = {
            "product_id": product.id,
            "name": product.name,
            "product_uom": product.uom_id.id,
            "product_uom_qty": qty,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
            "picking_id": picking.id,
            "priority": picking.priority,
            "picking_type_id": picking.picking_type_id.id,
        }
        vals.update(kwargs)
        return Move.create(vals)

    @classmethod
    def create_picking(
        cls, picking_type, products_info=False, confirm=False, assign=False, **kwargs
    ):
        """ Create and return a picking for the given picking_type."""
        Picking = cls.env["stock.picking"]
        vals = {
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
        }

        vals.update(kwargs)
        picking = Picking.create(vals)

        if products_info:
            for product_info in products_info:
                move_vals = product_info.copy()
                move_vals.update(picking=picking)
                move = cls.create_move(**move_vals)

        return picking

    @classmethod
    def create_classification(
        cls, name, alert_message=False, report_message=False, picking_types=False, report_types=False
    ):
        """ Create and return a warehouse classification."""
        Classification = cls.env["product.warehouse.classification"]
        classification_info = {
            "name": name,
            "alert_message": alert_message,
            "report_message": report_message,
            "picking_type_ids": [(6, 0, picking_types.mapped("id"))] if picking_types else False,
            "report_template_ids": [(6, 0, report_types.mapped("id"))] if report_types else False,
        }

        return Classification.create(classification_info)

    @classmethod
    def create_report(cls, name, report_name, model):
        """ Create and return a report."""
        Report = cls.env["ir.actions.report"]
        return Report.create({"name": name, "report_name": report_name, "model": model})
