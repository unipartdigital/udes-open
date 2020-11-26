from odoo.addons.udes_stock.tests import common


class TestDeliveryControl(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestDeliveryControl, cls).setUpClass()

        cls.Picking = cls.env["stock.picking"]

        cls.delivery_control_picking_type = cls.env.ref(
            "udes_delivery_control.picking_type_delivery_control"
        )

        cls.test_supplier = cls.create_partner("Test Supplier", supplier=True)

        delivery_control_picking_vals = {
            "name": "DC Pick",
            "partner_id": cls.test_supplier.id,
            "origin": "DCTesting",
            "u_loading_type": "unload",
        }
        cls.delivery_control_picking = cls.create_picking(
            cls.delivery_control_picking_type, **delivery_control_picking_vals
        )
